"""
基于向量的论文搜索模块
使用FAISS索引和BERT模型进行语义搜索
"""
import os
import json
import asyncio
import numpy as np
import faiss
import aiosqlite
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from ..db.config import db_config
from .model_manager import model_manager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class VectorSearcher:
    """基于向量的论文搜索器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.model = None
        self.index = None
        self.string_to_int_map = {}
        self.int_to_string_map = {}
        self._loading = False
        self._loaded = False
        
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent.parent
    
    async def ensure_loaded(self):
        """确保资源已加载"""
        if self._loaded:
            return
        
        if self._loading:
            # 如果正在加载，等待完成
            while self._loading:
                await asyncio.sleep(0.1)
            return
        
        self._loading = True
        try:
            logger.debug("[VectorSearch] ensure_loaded: start loading resources")
            await asyncio.to_thread(self._load_resources)
            self._loaded = True
            logger.info("[VectorSearch] 资源加载完成")
        except Exception as e:
            logger.exception(f"[VectorSearch] 加载搜索资源失败: {e}")
            self._loading = False
            raise
        finally:
            self._loading = False
    
    def _load_resources(self):
        """加载FAISS索引和ID映射"""
        try:
            # 加载FAISS索引
            index_path = db_config.get_index_path()
            if index_path.exists():
                self.index = faiss.read_index(str(index_path))
                logger.info(f"[VectorSearch] 成功加载FAISS索引 ntotal={self.index.ntotal} file={index_path}")
                
                # 记录索引基本信息
                logger.info(f"[VectorSearch] 索引类型: {type(self.index)}")
                logger.info(f"[VectorSearch] 索引维度: {self.index.d if hasattr(self.index, 'd') else 'unknown'}")
            else:
                logger.warning(f"FAISS索引文件不存在: {index_path}")
                return
            
            # 加载ID映射
            id_map_path = db_config.get_id_map_path()
            if id_map_path.exists():
                with open(id_map_path, 'r', encoding='utf-8') as f:
                    self.string_to_int_map = json.load(f)
                
                # 创建反向映射
                self.int_to_string_map = {v: k for k, v in self.string_to_int_map.items()}
                logger.info(f"[VectorSearch] 成功加载ID映射 size={len(self.string_to_int_map)} file={id_map_path}")
            else:
                logger.warning(f"ID映射文件不存在: {id_map_path}")
                return
            
            # 使用共享的BERT模型管理器
            self.model = model_manager.get_model()
            if self.model is None:
                logger.warning(f"[VectorSearch] 无法获取BERT模型")
                return
            logger.info(f"[VectorSearch] 成功获取共享BERT模型")
                
        except Exception as e:
            logger.exception(f"[VectorSearch] 加载搜索资源时出错: {str(e)}")
            self.index = None
            self.string_to_int_map = {}
            self.int_to_string_map = {}

    def _is_available(self) -> bool:
        """检查搜索服务是否可用"""
        return (
            self.index is not None and 
            self.string_to_int_map and 
            self.int_to_string_map and
            self.model is not None
        )

    async def vector_search(
        self, 
        query: str, 
        limit: int = 20, 
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        基于向量的语义搜索
        
        Args:
            query: 搜索查询
            limit: 返回结果数量
            offset: 偏移量
            filters: 搜索过滤器
            
        Returns:
            搜索结果列表
        """
        try:
            # 先尝试加载资源，再判断可用性（避免先判定不可用直接降级）
            logger.debug(f"[VectorSearch] 开始向量搜索 query='{query}' limit={limit} offset={offset}")
            await self.ensure_loaded()
            if not self._is_available():
                logger.warning("[VectorSearch] 服务不可用，降级为备用搜索")
                return await self._fallback_search(query, limit, offset, filters)
            
            # 将查询转换为向量
            logger.info(f"[VectorSearch] 查询: '{query}'")
            query_vector = self.model.encode([query], convert_to_numpy=True)[0]
            query_vector = query_vector.astype(np.float32)
            
            # 归一化查询向量
            faiss.normalize_L2(query_vector.reshape(1, -1))
            
            # 在FAISS索引中搜索
            search_limit = min(limit + offset + 50, self.index.ntotal)
            distances, neighbor_int_ids = self.index.search(query_vector.reshape(1, -1), search_limit)
            logger.info(f"[VectorSearch] 搜索完成，找到 {len(neighbor_int_ids[0])} 个候选结果")
            
            
            # 获取搜索结果 - 不过滤任何结果，先看看所有结果
            search_results = []
            valid_count = 0
            
            for i, int_id in enumerate(neighbor_int_ids[0]):
                if int_id == -1:  # 无效ID
                    logger.debug(f"[VectorSearch] 跳过无效ID: {int_id}")
                    continue
                
                # 获取字符串ID
                string_id = self.int_to_string_map.get(int_id)
                if not string_id:
                    logger.debug(f"[VectorSearch] 无法找到字符串ID: int_id={int_id}")
                    continue
                
                # 记录搜索结果
                valid_count += 1
                logger.info(f"[VectorSearch] 搜索结果 {i+1}: int_id={int_id}, distance={distances[0][i]:.6f}, string_id={string_id}")
                
                # 添加到结果中
                similarity_score = max(0.0, 1.0 - distances[0][i])
                search_results.append({
                    'paper_id': string_id,
                    'similarity_score': similarity_score,
                    'rank': i + 1,
                    'distance': distances[0][i]
                })
            
            logger.info(f"[VectorSearch] 搜索结果统计: 有效={valid_count}, 总计={len(search_results)}")
            
            # 从数据库获取详细信息
            if not search_results:
                logger.warning("[VectorSearch] 向量搜索没有找到结果")
                return []
            
            # 批量查询论文详细信息
            paper_ids = [result['paper_id'] for result in search_results]
            paper_details = await self._get_papers_details(paper_ids)
            logger.info(f"[VectorSearch] 数据库查询完成: {len(paper_details)}/{len(paper_ids)}")
            
            # 合并搜索结果和详细信息 - 采用和智能推荐相同的策略，不过滤无标题论文
            final_results = []
            for i, result in enumerate(search_results):
                paper_id = result['paper_id']
                if paper_id in paper_details:
                    paper_info = paper_details[paper_id]
                    title = paper_info.get('title', '')
                    paper_info.update({
                        'similarity_score': result['similarity_score'],
                        'rank': result['rank']
                    })
                    final_results.append(paper_info)
                    if len(final_results) <= 3:  # 只打印前3个论文的详细信息
                        logger.info(f"[VectorSearch] 论文 {len(final_results)}: paper_id={paper_id}, title='{title[:50] if title else '(无标题)'}...', similarity={result['similarity_score']:.3f}")
                else:
                    logger.debug(f"[VectorSearch] 论文详情未找到: paper_id={paper_id}")
            
            logger.info(f"[VectorSearch] 数据库查询结果: {len(paper_details)}/{len(paper_ids)}, 最终结果: {len(final_results)}")
            
            # 不再应用过滤器，返回所有搜索结果
            
            # 应用分页
            paginated_results = final_results[offset:offset + limit]
            
            logger.info(f"[VectorSearch] 完成 query='{query}' 返回 {len(paginated_results)} 条")
            return paginated_results
            
        except Exception as e:
            logger.exception(f"[VectorSearch] 向量搜索出错: {str(e)}")
            return await self._fallback_search(query, limit, offset, filters)

    async def _get_papers_details(self, paper_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取论文详细信息"""
        if not paper_ids:
            return {}
        
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                # 构建查询
                placeholders = ','.join('?' * len(paper_ids))
                query = f"""
                    SELECT id, short_id, title, authors, author_names, year, journal, abstract, 
                           keywords, doi, citation_count, download_count, url, reference_ids, 
                           cited_by, research_field, funding, journal_issn, host_organization_name, 
                           author_orcids, author_institutions, author_countries, fwci, 
                           citation_percentile, publication_date, primary_topic, topics, 
                           keywords_display, domain, crawl_timestamp
                    FROM works 
                    WHERE id IN ({placeholders})
                """
                
                async with db.execute(query, paper_ids) as cursor:
                    rows = await cursor.fetchall()
                
                # 格式化结果
                details = {}
                for row in rows:
                    if row:
                        paper_id = row[0]
                        details[paper_id] = self._format_paper_data(row)
                return details
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.exception(f"[VectorSearch] 获取论文详情时出错: {str(e)}")
            return {}

    def _format_paper_data(self, row) -> Dict[str, Any]:
        """格式化论文数据"""
        try:
            def parse_json(value, default):
                # 容错解析：支持已是list/dict、空字符串、非字符串等情况
                if value is None:
                    return default
                if isinstance(value, (list, dict)):
                    return value
                if isinstance(value, (int, float)):
                    return default
                if isinstance(value, str):
                    v = value.strip()
                    if not v:
                        return default
                    try:
                        return json.loads(v)
                    except Exception:
                        # 非JSON字符串，尝试以逗号分隔成列表（用于某些简单存储）
                        if "," in v:
                            parts = [p.strip() for p in v.split(",") if p.strip()]
                            return parts if parts else default
                        return default
                return default

            # 解析JSON字段（带容错）
            authors = parse_json(row[3] if len(row) > 3 else None, [])
            author_names = parse_json(row[4] if len(row) > 4 else None, [])
            keywords = parse_json(row[8] if len(row) > 8 else None, [])
            reference_ids = parse_json(row[13] if len(row) > 13 else None, [])
            cited_by = parse_json(row[14] if len(row) > 14 else None, [])
            author_orcids = parse_json(row[19] if len(row) > 19 else None, [])
            author_institutions = parse_json(row[20] if len(row) > 20 else None, [])
            author_countries = parse_json(row[21] if len(row) > 21 else None, [])
            topics = parse_json(row[26] if len(row) > 26 else None, [])
            keywords_display = parse_json(row[28] if len(row) > 28 else None, [])
            
            return {
                'id': row[0] if len(row) > 0 else '',
                'short_id': row[1] if len(row) > 1 else '',
                'title': (row[2] if len(row) > 2 else '') or '',
                'authors': authors,
                'author_names': author_names,
                'year': (row[5] if len(row) > 5 else 0) or 0,
                'journal': (row[6] if len(row) > 6 else '') or '',
                'abstract': (row[7] if len(row) > 7 else '') or '',
                'keywords': keywords,
                'doi': (row[9] if len(row) > 9 else '') or '',
                'citation_count': (row[10] if len(row) > 10 else 0) or 0,
                'download_count': (row[11] if len(row) > 11 else 0) or 0,
                'url': (row[12] if len(row) > 12 else '') or '',
                'reference_ids': reference_ids,
                'cited_by': cited_by,
                'research_field': (row[15] if len(row) > 15 else '') or '',
                'funding': (row[16] if len(row) > 16 else '') or '',
                'journal_issn': (row[17] if len(row) > 17 else '') or '',
                'host_organization_name': (row[18] if len(row) > 18 else '') or '',
                'author_orcids': author_orcids,
                'author_institutions': author_institutions,
                'author_countries': author_countries,
                'fwci': (row[22] if len(row) > 22 else 0.0) or 0.0,
                'citation_percentile': (row[23] if len(row) > 23 else 0.0) or 0.0,
                'publication_date': (row[24] if len(row) > 24 else '') or '',
                'primary_topic': (row[25] if len(row) > 25 else '') or '',
                'topics': topics,
                'keywords_display': keywords_display,
                'domain': (row[27] if len(row) > 27 else '') or '',
                'crawl_timestamp': (row[29] if len(row) > 29 else '') or ''
            }
        except Exception as e:
            logger.exception(f"[VectorSearch] 格式化论文数据时出错: {str(e)}")
            return {
                'id': (row[0] if row and len(row) > 0 else ''),
                'short_id': (row[1] if row and len(row) > 1 else ''),
                'title': (row[2] if row and len(row) > 2 else ''),
                'authors': [],
                'author_names': [],
                'year': (row[5] if row and len(row) > 5 else 0),
                'journal': (row[6] if row and len(row) > 6 else ''),
                'abstract': (row[7] if row and len(row) > 7 else ''),
                'keywords': [],
                'doi': (row[9] if row and len(row) > 9 else ''),
                'citation_count': (row[10] if row and len(row) > 10 else 0)
            }

    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """应用搜索过滤器"""
        if not filters:
            return results
        
        filtered_results = results.copy()
        
        # 年份过滤
        if 'year_from' in filters and filters['year_from']:
            filtered_results = [r for r in filtered_results if r.get('year', 0) >= filters['year_from']]
        
        if 'year_to' in filters and filters['year_to']:
            filtered_results = [r for r in filtered_results if r.get('year', 0) <= filters['year_to']]
        
        # 引用数过滤
        if 'min_citations' in filters and filters['min_citations']:
            filtered_results = [r for r in filtered_results if r.get('citation_count', 0) >= filters['min_citations']]
        
        # 研究领域过滤
        if 'research_field' in filters and filters['research_field']:
            field = filters['research_field'].lower()
            filtered_results = [r for r in filtered_results if field in r.get('research_field', '').lower()]
        
        # 期刊过滤
        if 'journal' in filters and filters['journal']:
            journal = filters['journal'].lower()
            filtered_results = [r for r in filtered_results if journal in r.get('journal', '').lower()]
        
        return filtered_results

    async def _fallback_search(self, query: str, limit: int, offset: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """备用搜索方法（基于文本匹配）"""
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                search_query = f"%{query.lower()}%"
                
                sql = """
                    SELECT id, short_id, title, authors, author_names, year, journal, abstract, 
                           keywords, doi, citation_count, download_count, url, reference_ids, 
                           cited_by, research_field, funding, journal_issn, host_organization_name, 
                           author_orcids, author_institutions, author_countries, fwci, 
                           citation_percentile, publication_date, primary_topic, topics, 
                           keywords_display, domain, crawl_timestamp
                    FROM works 
                    WHERE (LOWER(title) LIKE ? OR LOWER(abstract) LIKE ? OR LOWER(authors) LIKE ?)
                    AND title IS NOT NULL AND title != ''
                    ORDER BY citation_count DESC
                    LIMIT ?
                """
                
                async with db.execute(sql, (search_query, search_query, search_query, limit + offset)) as cursor:
                    rows = await cursor.fetchall()
                
                results = []
                for row in rows:
                    if row:
                        paper_data = self._format_paper_data(row)
                        paper_data['similarity_score'] = 0.5  # 默认相似度
                        results.append(paper_data)
                
                # 应用过滤器
                if filters:
                    results = self._apply_filters(results, filters)
                
                # 应用分页
                return results[offset:offset + limit]
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.exception(f"[VectorSearch] 备用搜索出错: {str(e)}")
            return []

    async def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """获取搜索建议（基于向量相似度）"""
        try:
            if not self._is_available():
                return await self._fallback_suggestions(query, limit)
            
            # 确保资源已加载
            await self.ensure_loaded()
            
            # 将查询转换为向量
            query_vector = self.model.encode([query], convert_to_numpy=True)[0]
            query_vector = query_vector.astype(np.float32)
            faiss.normalize_L2(query_vector.reshape(1, -1))
            
            # 搜索相似的论文标题
            distances, neighbor_int_ids = self.index.search(
                query_vector.reshape(1, -1), 
                min(limit * 3, self.index.ntotal)
            )
            
            suggestions = []
            for int_id in neighbor_int_ids[0]:
                if int_id == -1:
                    continue
                
                string_id = self.int_to_string_map.get(int_id)
                if not string_id:
                    continue
                
                # 获取论文标题
                db = await aiosqlite.connect(self.db_path)
                try:
                    async with db.execute("SELECT title FROM works WHERE id = ?", (string_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0]:
                            suggestions.append(row[0])
                            if len(suggestions) >= limit:
                                break
                finally:
                    await db.close()
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.exception(f"[VectorSearch] 获取搜索建议出错: {str(e)}")
            return await self._fallback_suggestions(query, limit)

    async def _fallback_suggestions(self, query: str, limit: int) -> List[str]:
        """备用搜索建议方法"""
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                search_query = f"%{query.lower()}%"
                sql = """
                    SELECT DISTINCT title FROM works 
                    WHERE LOWER(title) LIKE ? 
                    ORDER BY citation_count DESC 
                    LIMIT ?
                """
                
                async with db.execute(sql, (search_query, limit)) as cursor:
                    rows = await cursor.fetchall()
                
                return [row[0] for row in rows if row[0]]
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.exception(f"[VectorSearch] 备用搜索建议出错: {str(e)}")
            return []


# 全局搜索器实例
vector_searcher = VectorSearcher(str(db_config.get_database_path()))
