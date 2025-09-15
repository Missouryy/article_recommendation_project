"""
搜索API接口
"""
import time
import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, Depends, HTTPException
from ..models.paper import SearchRequest, SearchResponse, PaperSummary, SearchFilters
from ..models.user import User
from ..api.auth import get_current_user, get_current_user_optional
from ..db.database import db, user_manager
from ..algorithms.vector_search import vector_searcher
from ..algorithms.recommender import rerank_search_results

router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("/", response_model=SearchResponse, summary="论文搜索")
async def search_papers(search_request: SearchRequest, current_user: Optional[User] = Depends(get_current_user_optional)):
    """
    论文搜索API - 基于向量相似度（默认）并兼容传统方式
    
    支持多种搜索模式：
    - **vector**: 向量搜索（默认）- 基于BERT语义相似度
    - **hybrid**: 混合搜索 - 向量搜索 + 文本匹配合并
    - **semantic**: 语义搜索（传统）
    - **exact**: 精确搜索（传统）
    
    排序选项：
    - **relevance**: 相关度排序（默认，使用relevance_score）
    - **date**: 发表时间排序
    - **citation**: 引用数排序
    - **truth_value**: 真值分数排序
    """
    start_time = time.time()

    results: List[Dict[str, Any]] = []

    try:
        # 调试起点
        print(f"[VectorSearch][API] start query='{search_request.query}' type='{search_request.search_type}' limit={search_request.limit} offset={search_request.offset}")
        if search_request.search_type in ("vector", "hybrid"):
            # 确保向量搜索资源已加载
            try:
                await vector_searcher.ensure_loaded()
            except Exception as e:
                print(f"[VectorSearch][API] 向量搜索资源加载失败: {e}")
                # 如果向量搜索不可用，降级为文本搜索
                search_request.search_type = "semantic"
            
            # 使用向量搜索（先不分页，获取更大候选集以便后续排序/合并）
            vector_results = []
            if search_request.search_type in ("vector", "hybrid"):
                vector_results = await vector_searcher.vector_search(
                    query=search_request.query,
                    limit=search_request.limit + search_request.offset + 50,
                    offset=0,
                    filters=search_request.filters
                )
                
            # 若因资源未就绪被降级为文本，做一次提示（不抛错）
            if vector_results and isinstance(vector_results[0], dict) and 'similarity_score' not in vector_results[0]:
                print("[VectorSearch][API] vector path downgraded (no similarity_score in first item)")
            # 打印前70条的id与title
            try:
                preview = []
                for x in vector_results[:70]:
                    pid = x.get('id') or x.get('paper_id')
                    title = (x.get('title') or '')
                    preview.append({ 'id': pid, 'title': title[:120] })
                print(f"[VectorSearch][API] vector preview (top {len(preview)}): {preview}")
            except Exception as e:
                print(f"[VectorSearch][API] vector preview error: {e}")

            # 将相似度映射为通用的relevance_score，便于统一排序
            for item in vector_results:
                if 'similarity_score' in item and 'relevance_score' not in item:
                    item['relevance_score'] = float(item.get('similarity_score') or 0.0)

            results = vector_results
            print(f"[VectorSearch][API] vector candidates={len(results)}")
            

            if search_request.search_type == "hybrid":
                # 传统文本搜索作为补充信号
                text_results = await perform_search(
                    query=search_request.query,
                    search_type="exact",
                    filters=search_request.filters
                )
                # 文本结果补充relevance_score（若无）
                for tr in text_results:
                    tr.setdefault('relevance_score', 0.3)
                results = merge_search_results(results, text_results)
                print(f"[VectorSearch][API] hybrid merged={len(results)}")
        else:
            # 使用传统方法
            results = await perform_search(
                query=search_request.query,
                search_type=search_request.search_type,
                filters=search_request.filters
            )
            print(f"[VectorSearch][API] legacy results={len(results)}")
    except Exception as e:
        # 向量路径出错时兜底到传统方式，避免后端报错
        print(f"[VectorSearch][API] error in vector path: {e}, fallback to legacy")
        results = await perform_search(
            query=search_request.query,
            search_type="hybrid",
            filters=search_request.filters
        )
    
    # 为结果补充真值分数（用于真值展示与排序）
    try:
        _enrich_truth_scores(sorted_results := results)  # 先声明变量以便日志与后续处理
    except Exception as e:
        print(f"[VectorSearch][API] enrich truth scores failed: {e}")

    # 应用排序
    sorted_results = apply_sorting(
        results=results,
        sort_by=search_request.sort_by,
        sort_order=search_request.sort_order
    )
    print(f"[VectorSearch][API] sorted_results={len(sorted_results)}")

    # 规范化字段，避免后续重排/模型校验因 dict 元素报错
    def _to_str_list(x):
        if x is None:
            return []
        out = []
        for item in x if isinstance(x, (list, tuple)) else []:
            if isinstance(item, dict):
                name = item.get('name') or item.get('title') or item.get('value')
                if name:
                    out.append(str(name))
            else:
                out.append(str(item))
        return out

    for r in sorted_results:
        if isinstance(r.get('author_names'), (list, tuple)):
            r['author_names'] = _to_str_list(r.get('author_names'))
        elif 'authors' in r and isinstance(r.get('authors'), (list, tuple)):
            # 退化为从 authors 提取 name
            r['author_names'] = _to_str_list(r.get('authors'))
        else:
            r.setdefault('author_names', [])

        if isinstance(r.get('keywords'), (list, tuple)):
            r['keywords'] = _to_str_list(r.get('keywords'))
        else:
            r.setdefault('keywords', [])

        if not isinstance(r.get('research_field'), str):
            r['research_field'] = str(r.get('research_field') or '')
    
    # 如果用户已登录，且当前为相关度排序，才应用个性化重排序（避免覆盖用户选择的排序）
    if current_user and (search_request.sort_by or "relevance") == "relevance":
        user_data = await user_manager.get_user_by_id(current_user.id)
        if user_data:
            print(f"[VectorSearch][API] start rerank for user={current_user.id}")
            sorted_results = rerank_search_results(
                user_id=current_user.id,
                results=sorted_results,
                user_data=user_data
            )
            print(f"[VectorSearch][API] rerank done count={len(sorted_results)}")
            # 尊重前端 sort_order：个性化重排默认降序，如为升序则反转
            if (search_request.sort_order or "desc") == "asc":
                sorted_results = list(reversed(sorted_results))
            
            # 记录搜索历史
            await user_manager.add_search_history(current_user.id, search_request.query)
    
    # 分页
    total = len(sorted_results)
    paginated_results = sorted_results[search_request.offset:search_request.offset + search_request.limit]
    print(f"[VectorSearch][API] page size={len(paginated_results)} offset={search_request.offset}")
    
    # 转换为PaperSummary格式
    paper_summaries = []
    for result in paginated_results:
        summary = PaperSummary(
            id=result.get("id", result.get("paper_id", "")),
            short_id=result.get("short_id", ""),
            title=result.get("title", ""),
            author_names=result.get("author_names", []),
            year=result.get("year", 0),
            journal=result.get("journal", ""),
            citation_count=result.get("citation_count", 0),
            truth_value_score=result.get("truth_value_score"),
            research_field=result.get("research_field", "")
        )
        paper_summaries.append(summary)
    
    execution_time = time.time() - start_time
    
    return SearchResponse(
        papers=paper_summaries,
        total=total,
        query=search_request.query,
        search_type=search_request.search_type,
        filters=search_request.filters,
        execution_time=round(execution_time, 3)
    )

def merge_search_results(vector_results: List[Dict[str, Any]], text_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并向量搜索结果和文本搜索结果"""
    # 使用字典去重，优先保留向量搜索结果
    merged = {}
    
    # 先添加向量搜索结果
    for result in vector_results:
        paper_id = result.get('id') or result.get('paper_id')
        if paper_id:
            merged[paper_id] = result
    
    # 再添加文本搜索结果（如果不存在）
    for result in text_results:
        paper_id = result.get('id') or result.get('paper_id')
        if paper_id and paper_id not in merged:
            # 为文本搜索结果添加默认相似度分数
            result['similarity_score'] = 0.3
            result.setdefault('relevance_score', 0.3)
            merged[paper_id] = result
    
    # 按相似度/相关度排序
    values = list(merged.values())
    for v in values:
        if 'relevance_score' not in v:
            try:
                v['relevance_score'] = float(v.get('similarity_score') or 0.0)
            except Exception:
                v['relevance_score'] = 0.0
    # 防止出现不可比较项导致的排序异常
    return sorted(values, key=lambda x: (x.get('relevance_score') or 0.0), reverse=True)

@router.get("/suggestions", summary="搜索建议")
async def get_search_suggestions(
    q: str = Query(..., description="查询前缀"),
    limit: int = Query(10, description="建议数量限制")
):
    """
    获取搜索建议/自动补全 - 优先向量，失败回退文本
    
    - **q**: 用户输入的查询前缀
    - **limit**: 返回建议的最大数量
    """
    # 先尝试向量建议
    try:
        suggestions = await vector_searcher.get_search_suggestions(q, limit)
        return {"suggestions": suggestions}
    except Exception:
        # 回退到传统方式
        try:
            suggestions = []
            q_lower = q.lower()
            papers = await db.get_papers(limit=200)
            for paper in papers:
                title = (paper.get("title") or "").lower()
                if title.startswith(q_lower):
                    suggestions.append(paper["title"])  # 原始大小写
                for keyword in paper.get("keywords", []):
                    if isinstance(keyword, str) and keyword.lower().startswith(q_lower):
                        suggestions.append(keyword)
                for author_name in paper.get("author_names", []):
                    if isinstance(author_name, str) and author_name.lower().startswith(q_lower):
                        suggestions.append(author_name)
            unique_suggestions = list(dict.fromkeys(suggestions))[:limit]
            return {"suggestions": unique_suggestions}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取搜索建议失败: {str(e)}")

@router.get("/filters", summary="获取可用过滤器")
async def get_available_filters():
    """
    获取可用的搜索过滤器选项
    """
    # 从数据库中提取所有可能的过滤器值
    papers = await db.get_papers(limit=1000)  # 获取更多论文用于统计
    years = sorted(set(paper["year"] for paper in papers if paper["year"]), reverse=True)
    journals = sorted(set(paper["journal"] for paper in papers if paper["journal"]))
    research_fields = sorted(set(paper["research_field"] for paper in papers if paper["research_field"]))
    authors = []
    
    for paper in papers:
        if paper["author_names"]:
            authors.extend(paper["author_names"])
    unique_authors = sorted(set(authors))
    
    return {
        "years": {
            "min": min(years),
            "max": max(years),
            "available": years[:10]  # 最近10年
        },
        "journals": journals,
        "research_fields": research_fields,
        "authors": unique_authors[:50]  # 前50个作者
    }

@router.get("/trending", summary="热门搜索")
async def get_trending_searches(limit: int = Query(10, description="热门搜索数量")):
    """
    获取热门搜索词
    """
    # 模拟热门搜索数据
    trending_searches = [
        {"query": "深度学习", "count": 156},
        {"query": "机器学习", "count": 134},
        {"query": "自然语言处理", "count": 98},
        {"query": "计算机视觉", "count": 87},
        {"query": "推荐系统", "count": 76},
        {"query": "图神经网络", "count": 65},
        {"query": "知识图谱", "count": 54},
        {"query": "联邦学习", "count": 43},
        {"query": "强化学习", "count": 38},
        {"query": "预训练模型", "count": 32}
    ]
    
    return {
        "trending": trending_searches[:limit],
        "updated_at": "2023-12-01T10:00:00Z"
    }

@router.get("/history", summary="搜索历史")
async def get_search_history(
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, description="历史记录数量")
):
    """
    获取用户的搜索历史
    """
    history_queries = await user_manager.get_search_history(current_user.id, limit)
    
    return {
        "history": [{"query": query, "timestamp": ""} for query in history_queries],
        "total": len(history_queries)
    }

@router.delete("/history", summary="清除搜索历史")
async def clear_search_history(current_user: User = Depends(get_current_user)):
    """
    清除用户的搜索历史
    """
    success = await user_manager.clear_search_history(current_user.id)
    
    if success:
        return {"message": "搜索历史已清除"}
    else:
        return {"message": "搜索历史已经为空"}

# 辅助函数
async def perform_search(query: str, search_type: str = "hybrid", filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    执行搜索逻辑
    - hybrid: 使用数据库的加权混合相关度
    - semantic/exact: 暂时回退到加权混合（可扩展至向量语义/精确匹配）
    """
    # 当前三个模式均走统一的加权混合召回+打分
    results = await db.search_papers(query, filters)
    return results

def hybrid_search(query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    混合搜索：在标题、作者、关键词、摘要中搜索
    """
    results = []
    query_words = query.lower().split()
    
    for paper in db.papers:
        relevance_score = 0.0
        
        # 搜索标题
        title_matches = sum(1 for word in query_words if word in paper["title"].lower())
        relevance_score += title_matches * 3.0  # 标题匹配权重最高
        
        # 搜索作者
        for author_name in paper["author_names"]:
            author_matches = sum(1 for word in query_words if word in author_name.lower())
            relevance_score += author_matches * 2.0
        
        # 搜索关键词
        for keyword in paper["keywords"]:
            keyword_matches = sum(1 for word in query_words if word in keyword.lower())
            relevance_score += keyword_matches * 2.5
        
        # 搜索摘要
        abstract_matches = sum(1 for word in query_words if word in paper["abstract"].lower())
        relevance_score += abstract_matches * 1.0
        
        # 搜索期刊
        journal_matches = sum(1 for word in query_words if word in paper["journal"].lower())
        relevance_score += journal_matches * 1.5
        
        if relevance_score > 0:
            paper_copy = paper.copy()
            paper_copy["relevance_score"] = relevance_score
            results.append(paper_copy)
    
    # 应用过滤器
    if filters:
        results = apply_filters(results, filters)
    
    return results

def semantic_search(query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    语义搜索：处理长句和段落查询
    """
    results = []
    query_lower = query.lower()
    
    for paper in db.papers:
        # 简化的语义匹配 - 检查查询是否作为子串出现在文本中
        semantic_score = 0.0
        
        # 在摘要中寻找语义相关内容
        if query_lower in paper["abstract"].lower():
            semantic_score += 5.0
        
        # 检查标题的语义相关性
        if query_lower in paper["title"].lower():
            semantic_score += 3.0
        
        # 检查关键词组合的语义相关性
        keywords_text = " ".join(paper["keywords"]).lower()
        if query_lower in keywords_text:
            semantic_score += 4.0
        
        if semantic_score > 0:
            paper_copy = paper.copy()
            paper_copy["relevance_score"] = semantic_score
            results.append(paper_copy)
    
    # 应用过滤器
    if filters:
        results = apply_filters(results, filters)
    
    return results

def exact_search(query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    精确搜索：严格匹配查询词
    """
    results = []
    query_lower = query.lower().strip()
    
    for paper in db.papers:
        exact_score = 0.0
        
        # 精确匹配标题
        if query_lower == paper["title"].lower():
            exact_score += 10.0
        elif query_lower in paper["title"].lower():
            exact_score += 5.0
        
        # 精确匹配作者
        for author_name in paper["author_names"]:
            if query_lower == author_name.lower():
                exact_score += 8.0
            elif query_lower in author_name.lower():
                exact_score += 3.0
        
        # 精确匹配关键词
        for keyword in paper["keywords"]:
            if query_lower == keyword.lower():
                exact_score += 7.0
        
        # 精确匹配DOI
        if paper.get("doi") and query_lower == paper["doi"].lower():
            exact_score += 10.0
        
        if exact_score > 0:
            paper_copy = paper.copy()
            paper_copy["relevance_score"] = exact_score
            results.append(paper_copy)
    
    # 应用过滤器
    if filters:
        results = apply_filters(results, filters)
    
    return results

def apply_filters(results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    应用搜索过滤器
    """
    filtered_results = results.copy()
    
    # 年份过滤
    if filters.get("year_min"):
        filtered_results = [r for r in filtered_results if r["year"] >= filters["year_min"]]
    if filters.get("year_max"):
        filtered_results = [r for r in filtered_results if r["year"] <= filters["year_max"]]
    
    # 期刊过滤
    if filters.get("journals"):
        journal_names = [j.lower() for j in filters["journals"]]
        filtered_results = [r for r in filtered_results if r["journal"].lower() in journal_names]
    
    # 研究领域过滤
    if filters.get("research_fields"):
        field_names = [f.lower() for f in filters["research_fields"]]
        filtered_results = [r for r in filtered_results if r["research_field"].lower() in field_names]
    
    # 最小引用数过滤
    if filters.get("min_citations"):
        filtered_results = [r for r in filtered_results if r["citation_count"] >= filters["min_citations"]]
    
    # 最小真值分数过滤
    if filters.get("min_truth_value"):
        filtered_results = [r for r in filtered_results if r.get("truth_value_score", 0) >= filters["min_truth_value"]]
    
    # 作者过滤
    if filters.get("authors"):
        author_names = [a.lower() for a in filters["authors"]]
        filtered_results = [
            r for r in filtered_results 
            if any(author.lower() in author_names for author in r["author_names"])
        ]
    
    return filtered_results

def apply_sorting(results: List[Dict[str, Any]], sort_by: str = "relevance", sort_order: str = "desc") -> List[Dict[str, Any]]:
    """
    应用排序
    """
    reverse = sort_order == "desc"
    
    if sort_by == "date":
        return sorted(results, key=lambda x: x["year"], reverse=reverse)
    elif sort_by == "citation":
        return sorted(results, key=lambda x: x["citation_count"], reverse=reverse)
    elif sort_by == "truth_value":
        return sorted(results, key=lambda x: x.get("truth_value_score", 0), reverse=reverse)
    else:  # relevance
        return sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=reverse)

def _resolve_truth_db_path() -> Optional[str]:
    """尽量寻找真值SQLite路径；找不到时返回None，不抛错。"""
    try:
        env_path = os.getenv("TRUTH_DB_PATH")
        if env_path and os.path.exists(env_path):
            return env_path
        here = Path(__file__).resolve()
        candidates: List[Path] = []
        try:
            candidates.append(here.parents[3] / "truth_value_calculation" / "forged_output_merged_v2.db")
            candidates.append(here.parents[3] / "truth_value_calculation" / "data" / "forged_output_merged_v2.db")
        except Exception:
            pass
        candidates.append(Path.cwd() / "truth_value_calculation" / "forged_output_merged_v2.db")
        candidates.append(Path.cwd() / "truth_value_calculation" / "data" / "forged_output_merged_v2.db")
        for p in candidates:
            try:
                if p.exists():
                    return str(p)
            except Exception:
                continue
        return None
    except Exception:
        return None

def _enrich_truth_scores(results: List[Dict[str, Any]]):
    """为结果补充 truth_value_score（0-100）。若找不到真值库或查询异常则静默跳过，不进行任何估算。"""
    if not results:
        return
    db_path = _resolve_truth_db_path()
    if not db_path or not os.path.exists(db_path):
        return
    try:
        # 收集 short_id 列表
        sids: List[str] = []
        for r in results:
            sid = r.get("short_id")
            # 尝试从 id 提取短ID（如 'https://openalex.org/W123' -> 'W123'）
            if not sid:
                rid = r.get("id") or r.get("paper_id")
                if isinstance(rid, str) and ("openalex.org/" in rid or rid.startswith("http")):
                    sid = rid.rstrip("/").split("/")[-1]
            if isinstance(sid, str) and sid:
                sids.append(sid)
        # 去重并限制一次查询规模
        sids = list(dict.fromkeys(sids))
        if not sids:
            return

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # 真值表名
            table = "truth_agg_results"
            # 构造 IN 查询
            placeholders = ",".join(["?"] * len(sids))
            sql = f"SELECT short_id, truth_score_pct FROM {table} WHERE short_id IN ({placeholders})"
            cur.execute(sql, sids)
            rows = cur.fetchall()
            sid_to_score100 = {}
            for row in rows or []:
                try:
                    pct = float(row["truth_score_pct"]) if row["truth_score_pct"] is not None else None
                    if pct is not None:
                        sid_to_score100[str(row["short_id"])]= round(pct, 1)  # 0-100 量纲
                except Exception:
                    continue
            # 写回已有真值
            for r in results:
                sid = r.get("short_id")
                if not sid and isinstance(r.get("id"), str):
                    rid = r.get("id")
                    if "openalex.org/" in rid or rid.startswith("http"):
                        sid = rid.rstrip("/").split("/")[-1]
                if sid and sid in sid_to_score100:
                    r["truth_value_score"] = sid_to_score100[sid]
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        # 静默失败
        return
