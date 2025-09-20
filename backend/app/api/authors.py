"""
作者相关API接口 - 使用 author_db.db 学者库
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from ..models.paper import Author, AuthorSummary, PaperSummary
from ..models.user import User
from ..api.auth import get_current_user
from ..db.database import db, user_manager
from ..db.author_database import author_db

router = APIRouter(prefix="/authors", tags=["作者"])

@router.get("/search", response_model=List[AuthorSummary], summary="搜索作者")
async def search_authors(
    query: str = Query(..., description="作者姓名搜索词"),
    limit: int = Query(20, description="返回数量限制")
):
    """
    搜索作者（直接读取 author_db.db）
    """
    results = await author_db.search_authors(query, limit)
    return [AuthorSummary(**item) for item in results]

@router.get("/{author_name}", response_model=Author, summary="获取作者详情")
async def get_author_detail(author_name: str):
    """
    获取作者详细信息
    
    - **author_name**: 作者姓名
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    # 从作者库读取
    author_info = await author_db.get_author_by_name(author_name)
    if not author_info:
        raise HTTPException(status_code=404, detail="作者不存在")
    
    return Author(**author_info)

@router.get("/{author_name}/papers", response_model=List[PaperSummary], summary="获取作者论文")
async def get_author_papers(
    author_name: str,
    limit: int = Query(20, description="返回数量限制"),
    sort_by: str = Query("year", description="排序方式: year, citation"),
    order: str = Query("desc", description="排序顺序: asc, desc")
):
    """
    获取作者发表的论文列表
    
    - **author_name**: 作者姓名
    - **limit**: 论文数量限制
    - **sort_by**: 排序方式（year: 发表年份, citation: 引用数）
    - **order**: 排序顺序（asc: 升序, desc: 降序）
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    papers = await db.get_papers_by_author(author_name)
    
    if not papers:
        raise HTTPException(status_code=404, detail="未找到该作者的论文")
    
    # 排序
    reverse = order == "desc"
    if sort_by == "citation":
        papers = sorted(papers, key=lambda x: x.get("citation_count", 0), reverse=reverse)
    else:  # year
        papers = sorted(papers, key=lambda x: x.get("year", 0), reverse=reverse)
    
    # 限制数量
    papers = papers[:limit]
    
    # 转换为PaperSummary格式
    paper_summaries = []
    for paper in papers:
        summary = PaperSummary(
            id=paper["id"],
            short_id=paper.get("short_id"),
            title=paper["title"],
            author_names=paper["author_names"],
            year=paper["year"],
            journal=paper["journal"],
            citation_count=paper["citation_count"],
            truth_value_score=paper.get("truth_value_score"),
            research_field=paper["research_field"]
        )
        paper_summaries.append(summary)
    
    return paper_summaries

@router.get("/{author_name}/statistics", summary="获取作者统计信息")
async def get_author_statistics(author_name: str):
    """
    获取作者的详细统计信息
    
    - **author_name**: 作者姓名
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    papers = await db.get_papers_by_author(author_name)
    
    if not papers:
        raise HTTPException(status_code=404, detail="未找到该作者的论文")
    
    # 计算统计信息
    years = [paper["year"] for paper in papers if paper["year"]]
    citations_per_year = {}
    papers_per_year = {}
    total_citations = 0
    
    for paper in papers:
        year = paper["year"]
        citations = paper.get("citation_count", 0)
        
        if year:
            papers_per_year[year] = papers_per_year.get(year, 0) + 1
            citations_per_year[year] = citations_per_year.get(year, 0) + citations
        total_citations += citations
    
    # 研究领域分布
    research_fields = {}
    for paper in papers:
        field = paper.get("research_field") or paper.get("primary_topic") or paper.get("domain")
        if field:
            research_fields[field] = research_fields.get(field, 0) + 1
    
    # 期刊分布
    journals = {}
    for paper in papers:
        journal = paper.get("journal")
        if journal:
            journals[journal] = journals.get(journal, 0) + 1
    
    # 计算h-index
    citations_list = sorted([p.get("citation_count", 0) for p in papers], reverse=True)
    h_index = 0
    for i, citations in enumerate(citations_list, 1):
        if citations >= i:
            h_index = i
        else:
            break
    
    return {
        "author_name": author_name,
        "total_papers": len(papers),
        "total_citations": total_citations,
        "average_citations_per_paper": round(total_citations / len(papers), 2) if papers else 0,
        "active_years": max(years) - min(years) + 1 if years else 0,
        "first_publication_year": min(years) if years else None,
        "latest_publication_year": max(years) if years else None,
        "h_index": h_index,
        "papers_per_year": papers_per_year,
        "citations_per_year": citations_per_year,
        "research_fields": research_fields,
        "journal_distribution": journals
    }

@router.get("/{author_name}/career-timeline", summary="获取作者学术生涯轨迹")
async def get_author_career_timeline(author_name: str):
    """
    获取作者的学术生涯轨迹数据（用于图表展示）
    
    - **author_name**: 作者姓名
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    papers = await db.get_papers_by_author(author_name)
    
    if not papers:
        raise HTTPException(status_code=404, detail="未找到该作者的论文")
    
    # 按年份组织数据
    timeline_data = {}
    for paper in papers:
        year = paper.get("year")
        if not year:
            continue
            
        if year not in timeline_data:
            timeline_data[year] = {
                "year": year,
                "papers_count": 0,
                "total_citations": 0,
                "papers": []
            }
        
        timeline_data[year]["papers_count"] += 1
        timeline_data[year]["total_citations"] += paper.get("citation_count", 0)
        timeline_data[year]["papers"].append({
            "id": paper["id"],
            "title": paper["title"],
            "journal": paper["journal"],
            "citations": paper.get("citation_count", 0)
        })
    
    # 转换为列表并排序
    timeline = sorted(timeline_data.values(), key=lambda x: x["year"])
    
    return {
        "author_name": author_name,
        "academic_timeline": timeline,
        "total_active_years": len(timeline)
    }

@router.post("/{author_name}/follow", summary="关注作者")
async def follow_author(
    author_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    关注作者
    
    - **author_name**: 作者姓名
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    # 检查作者是否存在
    papers = await db.get_papers_by_author(author_name)
    if not papers:
        raise HTTPException(status_code=404, detail="作者不存在")
    
    author_id = f"author_{author_name.replace(' ', '_')}"
    success = await user_manager.follow_author(current_user.id, author_id)
    if not success:
        raise HTTPException(status_code=400, detail="已经关注该作者")
    
    return {"message": "关注成功"}

@router.delete("/{author_name}/follow", summary="取消关注作者")
async def unfollow_author(
    author_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    取消关注作者
    
    - **author_name**: 作者姓名
    """
    # URL解码作者姓名
    author_name = author_name.replace("_", " ")
    
    author_id = f"author_{author_name.replace(' ', '_')}"
    success = await user_manager.unfollow_author(current_user.id, author_id)
    if not success:
        raise HTTPException(status_code=400, detail="未关注该作者")
    
    return {"message": "已取消关注"}

@router.get("/", response_model=List[AuthorSummary], summary="获取热门作者")
async def get_popular_authors(
    limit: int = Query(20, description="返回数量限制"),
    offset: int = Query(0, description="偏移量，用于分页")
):
    """
    获取热门作者列表（直接读取 author_db.db）
    """
    results = await author_db.get_popular_authors(limit, offset)
    return [AuthorSummary(**item) for item in results]
