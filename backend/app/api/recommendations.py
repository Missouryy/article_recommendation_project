"""
智能推荐API接口
提供个性化论文推荐服务
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import asyncio
import aiosqlite
import logging
from datetime import datetime

from .auth import get_current_user, get_current_user_optional
from ..models.user import User
from ..algorithms.intelligent_recommender import IntelligentRecommender
from ..db.config import db_config
from ..db.database import db, user_manager

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/recommendations", tags=["智能推荐"])

# 推荐系统实例（使用基于BERT向量的智能推荐）
recommender = IntelligentRecommender(str(db_config.get_database_path()))

# Pydantic模型定义
class RecommendationRequest(BaseModel):
    """推荐请求模型"""
    limit: int = Field(default=20, ge=1, le=50, description="推荐数量")
    include_reasons: bool = Field(default=True, description="是否包含推荐理由")
    refresh: bool = Field(default=False, description="是否强制刷新推荐")

class RecommendationResponse(BaseModel):
    """推荐响应模型"""
    paper_id: str
    short_id: Optional[str] = None  # 添加short_id字段
    title: str = Field(default="未知标题", description="论文标题")
    relevance_score: float = Field(description="相关性评分 (0-1)")
    importance_score: float = Field(description="重要度评分 (0-1)")
    citation_count: int = Field(default=0)
    year: Optional[int] = None
    journal: Optional[str] = None
    recommendation_reason: str = Field(default="")
    created_at: str

class TrendingTopicResponse(BaseModel):
    """热门主题响应模型"""
    topic: str
    paper_count: int
    average_citations: float
    trend_score: float

class RecommendationStatsResponse(BaseModel):
    """推荐统计响应模型"""
    total_recommendations_generated: int
    user_profile_completeness: float
    top_recommended_topics: List[Dict[str, Any]]
    recommendation_accuracy_estimate: float

@router.get("/", response_model=List[RecommendationResponse], summary="获取个性化推荐")
async def get_personalized_recommendations(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=50, description="推荐数量"),
    include_reasons: bool = Query(default=True, description="是否包含推荐理由"),
    refresh: bool = Query(default=False, description="是否强制刷新推荐")
):
    """
    获取用户的个性化论文推荐
    
    基于用户的历史行为、研究兴趣和论文重要度生成推荐列表。
    推荐算法综合考虑：
    - 用户阅读历史和收藏记录
    - 关注的作者和研究领域
    - 论文的引用数和影响力
    - 内容相似性和协同过滤
    
    Returns:
        推荐论文列表，按相关性评分排序
    """
    try:
        # 记录用户访问推荐页面的行为
        await user_manager.add_reading_history(current_user.id, "recommendation_page_visit")
        
        # 获取推荐结果 - 默认使用日常推荐
        recommendations = await recommender.get_daily_recommendations(
            user_id=current_user.id,
            limit=limit
        )
        
        if not recommendations:
            # 如果没有推荐结果，返回热门论文
            logger.warning(f"用户 {current_user.id} 未获得推荐结果，返回热门论文")
            popular_papers = await recommender.get_popular_recommendations(limit, 0)
            return [RecommendationResponse(
                paper_id=paper.get('paper_id', ''),
                short_id=paper.get('short_id'),
                title=paper.get('title') or '未知标题',
                relevance_score=paper.get('relevance_score', 0.5),
                importance_score=paper.get('importance_score', 0.5),
                citation_count=paper.get('citation_count', 0),
                year=paper.get('year'),
                journal=paper.get('journal'),
                recommendation_reason=paper.get('recommendation_reason', ''),
                created_at=paper.get('created_at', datetime.now().isoformat())
            ) for paper in popular_papers]
        
        # 获取推荐论文的详细信息
        enriched_recommendations = []
        for rec in recommendations:
            try:
                # 获取论文详细信息
                paper_detail = await db.get_paper_by_id(rec['paper_id'])
                if paper_detail:
                    enriched_rec = RecommendationResponse(
                        paper_id=rec['paper_id'],
                        short_id=paper_detail.get('short_id') or rec.get('short_id'),
                        title=paper_detail.get('title') or rec.get('title') or '未知标题',
                        relevance_score=rec.get('relevance_score', 0.5),
                        importance_score=rec.get('importance_score', 0.5),
                        citation_count=paper_detail.get('citation_count') or rec.get('citation_count') or 0,
                        year=paper_detail.get('year') or rec.get('year'),
                        journal=paper_detail.get('journal') or rec.get('journal'),
                        recommendation_reason=rec.get('recommendation_reason', '') if include_reasons else "",
                        created_at=rec.get('created_at', datetime.now().isoformat())
                    )
                    enriched_recommendations.append(enriched_rec)
            except Exception as e:
                logger.error(f"处理推荐论文 {rec['paper_id']} 时出错: {str(e)}")
                continue
        
        logger.info(f"为用户 {current_user.id} 生成了 {len(enriched_recommendations)} 条推荐")
        return enriched_recommendations
        
    except Exception as e:
        logger.error(f"生成推荐时出错 - 用户ID: {current_user.id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="推荐服务暂时不可用，请稍后重试")

@router.get("/daily", response_model=List[RecommendationResponse], summary="获取日常推荐")
async def get_daily_recommendations(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=50, description="推荐数量"),
    offset: int = Query(default=0, ge=0, description="偏移量（分页）"),
    include_reasons: bool = Query(default=True, description="是否包含推荐理由")
):
    """
    获取日常推荐
    
    基于前5篇收藏论文（权重1）和前10篇阅读历史（权重1.5）
    适合日常浏览，平衡了用户的阅读习惯和收藏偏好
    
    Returns:
        日常推荐论文列表，按相关性评分排序
    """
    try:
        # 记录用户访问推荐页面的行为
        await user_manager.add_reading_history(current_user.id, "daily_recommendation_visit")
        
        # 获取推荐结果
        recommendations = await recommender.get_daily_recommendations(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        if not recommendations:
            # 如果没有推荐结果，返回热门论文
            logger.warning(f"用户 {current_user.id} 未获得日常推荐结果，返回热门论文")
            popular_papers = await recommender.get_popular_recommendations(limit, offset)
            return [RecommendationResponse(
                paper_id=paper.get('paper_id', ''),
                short_id=paper.get('short_id'),
                title=paper.get('title') or '未知标题',
                relevance_score=paper.get('relevance_score', 0.5),
                importance_score=paper.get('importance_score', 0.5),
                citation_count=paper.get('citation_count', 0),
                year=paper.get('year'),
                journal=paper.get('journal'),
                recommendation_reason=paper.get('recommendation_reason', ''),
                created_at=paper.get('created_at', datetime.now().isoformat())
            ) for paper in popular_papers]
        
        # 转换为标准响应格式
        enriched_recommendations = []
        for rec in recommendations:
            try:
                enriched_rec = RecommendationResponse(
                    paper_id=rec['paper_id'],
                    short_id=rec.get('short_id'),
                    title=rec.get('title') or '未知标题',
                    relevance_score=rec.get('relevance_score', 0.5),
                    importance_score=rec.get('importance_score', 0.5),
                    citation_count=rec.get('citation_count', 0),
                    year=rec.get('year'),
                    journal=rec.get('journal'),
                    recommendation_reason=rec.get('recommendation_reason', '') if include_reasons else "",
                    created_at=rec.get('created_at', datetime.now().isoformat())
                )
                enriched_recommendations.append(enriched_rec)
            except Exception as e:
                logger.error(f"处理日常推荐论文 {rec['paper_id']} 时出错: {str(e)}")
                continue
        
        logger.info(f"为用户 {current_user.id} 生成了 {len(enriched_recommendations)} 条日常推荐")
        return enriched_recommendations
        
    except Exception as e:
        logger.error(f"生成日常推荐时出错 - 用户ID: {current_user.id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="日常推荐服务暂时不可用，请稍后重试")

@router.get("/preference", response_model=List[RecommendationResponse], summary="获取喜好推荐")
async def get_preference_recommendations(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=50, description="推荐数量"),
    offset: int = Query(default=0, ge=0, description="偏移量（分页）"),
    include_reasons: bool = Query(default=True, description="是否包含推荐理由")
):
    """
    获取喜好推荐
    
    基于10篇收藏论文（权重2）和前10篇阅读历史（权重1）
    更侧重于用户收藏的论文类型，适合深度研究
    
    Returns:
        喜好推荐论文列表，按相关性评分排序
    """
    try:
        # 记录用户访问推荐页面的行为
        await user_manager.add_reading_history(current_user.id, "preference_recommendation_visit")
        
        # 获取推荐结果
        recommendations = await recommender.get_preference_recommendations(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        if not recommendations:
            # 如果没有推荐结果，返回热门论文
            logger.warning(f"用户 {current_user.id} 未获得喜好推荐结果，返回热门论文")
            popular_papers = await recommender.get_popular_recommendations(limit, offset)
            return [RecommendationResponse(
                paper_id=paper.get('paper_id', ''),
                short_id=paper.get('short_id'),
                title=paper.get('title') or '未知标题',
                relevance_score=paper.get('relevance_score', 0.5),
                importance_score=paper.get('importance_score', 0.5),
                citation_count=paper.get('citation_count', 0),
                year=paper.get('year'),
                journal=paper.get('journal'),
                recommendation_reason=paper.get('recommendation_reason', ''),
                created_at=paper.get('created_at', datetime.now().isoformat())
            ) for paper in popular_papers]
        
        # 转换为标准响应格式
        enriched_recommendations = []
        for rec in recommendations:
            try:
                enriched_rec = RecommendationResponse(
                    paper_id=rec['paper_id'],
                    short_id=rec.get('short_id'),
                    title=rec.get('title') or '未知标题',
                    relevance_score=rec.get('relevance_score', 0.5),
                    importance_score=rec.get('importance_score', 0.5),
                    citation_count=rec.get('citation_count', 0),
                    year=rec.get('year'),
                    journal=rec.get('journal'),
                    recommendation_reason=rec.get('recommendation_reason', '') if include_reasons else "",
                    created_at=rec.get('created_at', datetime.now().isoformat())
                )
                enriched_recommendations.append(enriched_rec)
            except Exception as e:
                logger.error(f"处理喜好推荐论文 {rec['paper_id']} 时出错: {str(e)}")
                continue
        
        logger.info(f"为用户 {current_user.id} 生成了 {len(enriched_recommendations)} 条喜好推荐")
        return enriched_recommendations
        
    except Exception as e:
        logger.error(f"生成喜好推荐时出错 - 用户ID: {current_user.id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="喜好推荐服务暂时不可用，请稍后重试")

@router.get("/popular", response_model=List[RecommendationResponse], summary="获取热门推荐")
async def get_popular_recommendations(
    limit: int = Query(default=20, ge=1, le=50, description="推荐数量"),
    offset: int = Query(default=0, ge=0, description="偏移量（分页）"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取热门论文推荐
    
    基于引用数、发表时间等因素推荐热门论文，
    适用于新用户或作为个性化推荐的补充。
    
    Returns:
        热门论文列表，按重要度排序
    """
    try:
        # 获取热门推荐
        popular_papers = await recommender.get_popular_recommendations(limit, offset)
        
        # 转换为标准响应格式
        recommendations = []
        for paper in popular_papers:
            rec = RecommendationResponse(
                paper_id=paper.get('paper_id', ''),
                short_id=paper.get('short_id'),
                title=paper.get('title') or '未知标题',
                relevance_score=paper.get('relevance_score', 0.5),
                importance_score=paper.get('importance_score', 0.5),
                citation_count=paper.get('citation_count', 0),
                year=paper.get('year'),
                journal=paper.get('journal'),
                recommendation_reason=paper.get('recommendation_reason', ''),
                created_at=paper.get('created_at', datetime.now().isoformat())
            )
            recommendations.append(rec)
        
        logger.info(f"生成了 {len(recommendations)} 条热门推荐")
        return recommendations
        
    except Exception as e:
        logger.error(f"获取热门推荐时出错: {str(e)}")
        raise HTTPException(status_code=500, detail="获取热门推荐失败")

@router.get("/trending-topics", response_model=List[TrendingTopicResponse], summary="获取热门研究主题")
async def get_trending_topics(
    limit: int = Query(default=10, ge=1, le=20, description="主题数量"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取当前热门的研究主题
    
    分析最近发表的论文，识别热门研究方向和新兴领域。
    
    Returns:
        热门主题列表，按热度排序
    """
    try:
        trending_topics = await recommender.get_trending_topics(limit)
        
        response = []
        for topic in trending_topics:
            response.append(TrendingTopicResponse(
                topic=topic['topic'],
                paper_count=topic['paper_count'],
                average_citations=topic['average_citations'],
                trend_score=topic['trend_score']
            ))
        
        logger.info(f"获取了 {len(response)} 个热门主题")
        return response
        
    except Exception as e:
        logger.error(f"获取热门主题时出错: {str(e)}")
        raise HTTPException(status_code=500, detail="获取热门主题失败")

@router.get("/stats", response_model=RecommendationStatsResponse, summary="获取推荐统计信息")
async def get_recommendation_stats(
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的推荐统计信息（简化版）
    """
    try:
        # 简化的统计信息
        stats = RecommendationStatsResponse(
            total_recommendations_generated=10,  # 模拟数据
            user_profile_completeness=0.7,
            top_recommended_topics=[
                {"topic": "人工智能", "score": 0.8},
                {"topic": "机器学习", "score": 0.6}
            ],
            recommendation_accuracy_estimate=0.8
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"获取推荐统计信息时出错 - 用户ID: {current_user.id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")

@router.post("/feedback", summary="提供推荐反馈")
async def provide_recommendation_feedback(
    paper_id: str = Query(description="论文ID"),
    feedback_type: str = Query(description="反馈类型: like, dislike, not_relevant"),
    current_user: User = Depends(get_current_user)
):
    """
    为推荐结果提供反馈
    
    用户反馈将用于改进推荐算法的准确性。
    
    Args:
        paper_id: 被反馈的论文ID
        feedback_type: 反馈类型（喜欢、不喜欢、不相关）
        
    Returns:
        反馈确认信息
    """
    try:
        # 验证论文是否存在
        paper = await db.get_paper_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        
        # 验证反馈类型
        valid_feedback_types = ['like', 'dislike', 'not_relevant']
        if feedback_type not in valid_feedback_types:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的反馈类型。支持的类型: {', '.join(valid_feedback_types)}"
            )
        
        # 根据反馈类型执行相应操作
        if feedback_type == 'like':
            # 用户喜欢，添加到收藏或阅读历史
            await user_manager.add_bookmark(current_user.id, paper_id)
            await user_manager.add_reading_history(current_user.id, paper_id)
        elif feedback_type == 'dislike':
            # 用户不喜欢，记录负反馈（这里简化处理）
            pass
        elif feedback_type == 'not_relevant':
            # 不相关，记录负反馈
            pass
        
        logger.info(f"用户 {current_user.id} 对论文 {paper_id} 提供了 {feedback_type} 反馈")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "反馈已记录，感谢您的参与！",
                "feedback_type": feedback_type,
                "paper_id": paper_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理推荐反馈时出错 - 用户ID: {current_user.id}, 论文ID: {paper_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="处理反馈失败")

@router.get("/similar/{paper_id}", response_model=List[RecommendationResponse], summary="获取相似论文推荐")
async def get_similar_paper_recommendations(
    paper_id: str,
    limit: int = Query(default=10, ge=1, le=20, description="推荐数量"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    基于指定论文获取相似论文推荐
    
    分析论文的主题、关键词、作者等特征，
    推荐内容相似的其他论文。
    
    Args:
        paper_id: 基础论文ID
        limit: 推荐数量
        
    Returns:
        相似论文列表
    """
    try:
        # 验证论文是否存在
        base_paper = await db.get_paper_by_id(paper_id)
        if not base_paper:
            raise HTTPException(status_code=404, detail="指定的论文不存在")
        
        # 简化版相似论文推荐 - 基于论文的基本信息
        recommendations = []
        
        # 获取基础论文的信息来搜索相似论文
        try:
            db_conn = await aiosqlite.connect(str(db_config.get_database_path()))
            try:
                # 获取目标论文的领域和关键信息
                query = """
                    SELECT research_field, journal, topics, keywords_display, primary_topic
                    FROM works WHERE id = ?
                """
                async with db_conn.execute(query, (paper_id,)) as cursor:
                    paper_row = await cursor.fetchone()
                
                if paper_row:
                    research_field, journal, topics, keywords, primary_topic = paper_row
                    
                    # 构建相似性查询
                    conditions = []
                    params = []
                    
                    if research_field:
                        conditions.append("research_field = ?")
                        params.append(research_field)
                    
                    if journal:
                        conditions.append("journal = ?")
                        params.append(journal)
                    
                    if primary_topic:
                        conditions.append("primary_topic LIKE ?")
                        params.append(f"%{primary_topic}%")
                    
                    if conditions:
                        where_clause = " OR ".join(conditions)
                        similar_query = f"""
                            SELECT id, title, citation_count, year, journal
                            FROM works 
                            WHERE ({where_clause}) AND id != ?
                            ORDER BY citation_count DESC, year DESC
                            LIMIT ?
                        """
                        params.extend([paper_id, limit])
                        
                        async with db_conn.execute(similar_query, params) as cursor:
                            similar_rows = await cursor.fetchall()
                        
                        for row in similar_rows:
                            similar_id, title, citation_count, year, journal_name = row
                            
                            # 计算重要度评分
                            importance_score = min(1.0, (citation_count or 0) / 1000)
                            
                            rec = RecommendationResponse(
                                paper_id=similar_id,
                                short_id=similar_id,  # 这里相似论文的ID直接使用short_id
                                title=title or '未知标题',
                                relevance_score=0.8,  # 基础相似度分数
                                importance_score=importance_score,
                                citation_count=citation_count or 0,
                                year=year,
                                journal=journal_name,
                                recommendation_reason=f"与《{(base_paper.get('title') or '目标论文')[:50]}...》内容相似",
                                created_at=datetime.now().isoformat()
                            )
                            recommendations.append(rec)
                
            finally:
                await db_conn.close()
                
        except Exception as e:
            logger.error(f"查找相似论文时出错: {str(e)}")
        
        # 按重要度排序
        recommendations.sort(key=lambda x: x.importance_score, reverse=True)
        
        logger.info(f"为论文 {paper_id} 找到了 {len(recommendations)} 篇相似论文")
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取相似论文推荐时出错 - 论文ID: {paper_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="获取相似论文推荐失败")

@router.post("/refresh", summary="刷新用户推荐")
async def refresh_user_recommendations(
    current_user: User = Depends(get_current_user)
):
    """
    刷新用户的推荐缓存（简化版）
    """
    try:
        logger.info(f"用户 {current_user.id} 请求刷新推荐")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "推荐已刷新",
                "user_id": current_user.id,
                "refresh_time": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"刷新用户推荐时出错 - 用户ID: {current_user.id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="刷新推荐失败")

# 导入必要的模块已在文件开头处理
