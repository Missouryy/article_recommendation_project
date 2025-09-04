import os
import json
import numpy as np
import faiss
import aiosqlite
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from ..db.config import db_config

logger = logging.getLogger(__name__)

class IntelligentRecommender:
    """基于BERT向量相似度的智能推荐系统"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.model = None
        self.index = None
        self.string_to_int_map = {}
        self.int_to_string_map = {}
        
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent.parent
        
        # 加载资源
        self._load_resources()
    
    def _load_resources(self):
        """加载FAISS索引和ID映射"""
        try:
            # 加载FAISS索引
            index_path = db_config.get_index_path()
            if index_path.exists():
                self.index = faiss.read_index(str(index_path))
                logger.info(f"成功加载FAISS索引，包含 {self.index.ntotal} 个向量，使用文件: {index_path}")
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
                logger.info(f"成功加载ID映射，包含 {len(self.string_to_int_map)} 个映射，使用文件: {id_map_path}")
            else:
                logger.warning(f"ID映射文件不存在: {id_map_path}")
                return
            
            # 加载BERT模型
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("成功加载BERT模型")
            except Exception as e:
                logger.warning(f"加载BERT模型失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"加载资源时出错: {str(e)}")
            self.index = None
            self.string_to_int_map = {}
            self.int_to_string_map = {}

    async def get_daily_recommendations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取日常推荐
        基于前5篇收藏论文（权重1）和前10篇阅读历史（权重1.5）
        """
        try:
            if not self._is_available():
                logger.warning("向量推荐服务不可用，使用备用推荐")
                return await self._get_fallback_recommendations(limit, offset)
            
            db = await aiosqlite.connect(self.db_path)
            try:
                # 获取用户的收藏历史（最多5篇，有多少取多少）
                bookmark_query = """
                    SELECT paper_id FROM user_bookmarks 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC LIMIT 5
                """
                async with db.execute(bookmark_query, (user_id,)) as cursor:
                    bookmark_rows = await cursor.fetchall()
                    favorite_history = [row[0] for row in bookmark_rows]
                
                # 获取用户的阅读历史（最多10篇，有多少取多少，过滤系统记录）
                reading_query = """
                    SELECT paper_id FROM user_reading_history 
                    WHERE user_id = ? 
                    AND paper_id NOT LIKE '%_visit'
                    AND paper_id NOT LIKE 'recommendation_%'
                    AND paper_id LIKE 'W%'
                    ORDER BY created_at DESC LIMIT 10
                """
                async with db.execute(reading_query, (user_id,)) as cursor:
                    reading_rows = await cursor.fetchall()
                    read_history = [row[0] for row in reading_rows]
                
                # 调试信息
                logger.info(f"用户 {user_id} 的历史数据:")
                if favorite_history:
                    logger.info(f"收藏历史: {favorite_history[:3]}{'...' if len(favorite_history) > 3 else ''}")
                if read_history:
                    logger.info(f"阅读历史: {read_history[:3]}{'...' if len(read_history) > 3 else ''}")
                
                # 生成推荐（获取更多数量以支持分页）
                total_needed = limit + offset
                recommendations = await self._recommend_for_user(
                    db=db,
                    read_history=read_history,
                    favorite_history=favorite_history,
                    read_weight=1.5,
                    favorite_weight=1.0,
                    top_k=min(total_needed, 100),  # 最多生成100个
                    recommendation_type="日常推荐"
                )
                
                # 应用分页
                recommendations = recommendations[offset:offset + limit]
                
                logger.info(f"为用户 {user_id} 生成了 {len(recommendations)} 条日常推荐")
                return recommendations
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.error(f"生成日常推荐时出错: {str(e)}")
            return await self._get_fallback_recommendations(limit, offset)

    async def get_preference_recommendations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取喜好推荐
        基于10篇收藏论文（权重2）和前10篇阅读历史（权重1）
        """
        try:
            if not self._is_available():
                logger.warning("向量推荐服务不可用，使用备用推荐")
                return await self._get_fallback_recommendations(limit, offset)
            
            db = await aiosqlite.connect(self.db_path)
            try:
                # 获取用户的收藏历史（最多10篇，有多少取多少）
                bookmark_query = """
                    SELECT paper_id FROM user_bookmarks 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC LIMIT 10
                """
                async with db.execute(bookmark_query, (user_id,)) as cursor:
                    bookmark_rows = await cursor.fetchall()
                    favorite_history = [row[0] for row in bookmark_rows]
                
                # 获取用户的阅读历史（最多10篇，有多少取多少，过滤系统记录）
                reading_query = """
                    SELECT paper_id FROM user_reading_history
                    WHERE user_id = ?
                    AND paper_id NOT LIKE '%_visit'
                    AND paper_id NOT LIKE 'recommendation_%'
                    AND paper_id LIKE 'W%'
                    ORDER BY created_at DESC LIMIT 10
                """
                async with db.execute(reading_query, (user_id,)) as cursor:
                    reading_rows = await cursor.fetchall()
                    read_history = [row[0] for row in reading_rows]
                
                # 调试信息
                logger.info(f"用户 {user_id} 的历史数据:")
                if favorite_history:
                    logger.info(f"收藏历史: {favorite_history[:3]}{'...' if len(favorite_history) > 3 else ''}")
                if read_history:
                    logger.info(f"阅读历史: {read_history[:3]}{'...' if len(read_history) > 3 else ''}")
                
                # 生成推荐（获取更多数量以支持分页）
                total_needed = limit + offset
                recommendations = await self._recommend_for_user(
                    db=db,
                    read_history=read_history,
                    favorite_history=favorite_history,
                    read_weight=1.0,
                    favorite_weight=2.0,
                    top_k=min(total_needed, 100),  # 最多生成100个
                    recommendation_type="喜好推荐"
                )
                
                # 应用分页
                recommendations = recommendations[offset:offset + limit]
                
                logger.info(f"为用户 {user_id} 生成了 {len(recommendations)} 条喜好推荐")
                return recommendations
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.error(f"生成喜好推荐时出错: {str(e)}")
            return await self._get_fallback_recommendations(limit, offset)

    async def _recommend_for_user(
        self, 
        db: aiosqlite.Connection,
        read_history: List[str], 
        favorite_history: List[str],
        read_weight: float,
        favorite_weight: float,
        top_k: int,
        recommendation_type: str
    ) -> List[Dict[str, Any]]:
        """为用户生成推荐的核心逻辑"""
        try:
            # 如果用户没有任何历史，返回热门推荐
            if not read_history and not favorite_history:
                logger.info("用户历史为空，返回热门推荐")
                return await self._get_popular_recommendations(db, top_k, recommendation_type)
            
            # 收集历史论文的向量索引和权重
            history_int_ids = []
            weights = []
            missing_papers = []
            
            # Add bookmark history
            logger.info(f"处理收藏历史，共 {len(favorite_history)} 篇")
            for string_id in favorite_history:
                # Try direct match
                if string_id in self.string_to_int_map:
                    history_int_ids.append(self.string_to_int_map[string_id])
                    weights.append(favorite_weight)
                else:
                    # Try adding OpenAlex URL prefix
                    full_id = f"https://openalex.org/{string_id}"
                    if full_id in self.string_to_int_map:
                        history_int_ids.append(self.string_to_int_map[full_id])
                        weights.append(favorite_weight)
                        logger.info(f"论文ID {string_id} 使用完整URL格式找到: {full_id}")
                    else:
                        missing_papers.append(string_id)

            # Add reading history
            logger.info(f"处理阅读历史，共 {len(read_history)} 篇")
            for string_id in read_history:
                # Try direct match
                if string_id in self.string_to_int_map:
                    history_int_ids.append(self.string_to_int_map[string_id])
                    weights.append(read_weight)
                else:
                    # Try adding OpenAlex URL prefix
                    full_id = f"https://openalex.org/{string_id}"
                    if full_id in self.string_to_int_map:
                        history_int_ids.append(self.string_to_int_map[full_id])
                        weights.append(read_weight)
                        logger.info(f"论文ID {string_id} 使用完整URL格式找到: {full_id}")
                    else:
                        missing_papers.append(string_id)
            
            if missing_papers:
                logger.warning(f"有 {len(missing_papers)} 篇论文不在向量索引中: {missing_papers[:5]}{'...' if len(missing_papers) > 5 else ''}")
            
            # 如果没有找到任何有效的历史论文，返回热门推荐
            if not history_int_ids:
                logger.warning("用户历史中没有找到有效的论文向量，返回热门推荐")
                return await self._get_popular_recommendations(db, top_k, recommendation_type)
            
            # 按照vector_generator/test.py的范例实现向量推荐
            logger.info(f"找到 {len(history_int_ids)} 篇有效历史论文，开始生成用户画像向量")
            
            # 步骤1: 获取历史向量并计算加权平均值（参考test.py的实现）
            import numpy as np
            
            ids_to_reconstruct = np.array(history_int_ids, dtype='int64')
            
            # 使用IndexIDMap的内部基础索引进行reconstruct（参考test.py第88行）
            base_index = self.index.index
            history_vectors_list = [base_index.reconstruct(int(i)) for i in ids_to_reconstruct]
            history_vectors = np.array(history_vectors_list)
            
            # 计算加权平均向量（参考test.py第92-94行）
            weights_array = np.array(weights).reshape(-1, 1)
            user_profile_vector = np.sum(history_vectors * weights_array, axis=0) / np.sum(weights_array)
            
            # 转换为float32并归一化（参考test.py第97-99行）
            user_profile_vector_float32 = user_profile_vector.astype(np.float32)
            import faiss
            faiss.normalize_L2(user_profile_vector_float32.reshape(1, -1))
            
            logger.info("用户画像向量生成成功")
            
            # 步骤2: 使用用户画像向量在Faiss中进行搜索（参考test.py第104-110行）
            num_to_search = top_k + len(read_history) + len(favorite_history)
            logger.info(f"正在FAISS索引中搜索 {num_to_search} 个最相似的向量")
            
            # 使用转换后的float32向量进行搜索
            distances, neighbor_int_ids = self.index.search(user_profile_vector_float32.reshape(1, -1), num_to_search)
            
            # 步骤3: 过滤掉已知论文并格式化结果（参考test.py第112-130行）
            user_known_ids = set(read_history + favorite_history)
            recommended_ids = []
            
            logger.info("正在过滤已读和已收藏的论文")
            for int_id in neighbor_int_ids[0]:
                # Faiss可能会返回-1作为无效ID
                if int_id == -1:
                    continue
                    
                # 使用整数键进行查找
                string_id = self.int_to_string_map.get(int_id)
                if string_id and string_id not in user_known_ids:
                    recommended_ids.append(string_id)
                
                if len(recommended_ids) >= top_k:
                    break
            
            # 步骤4: 从数据库获取推荐论文的详细信息
            if not recommended_ids:
                logger.warning("向量搜索没有找到有效推荐，返回热门推荐")
                return await self._get_popular_recommendations(db, top_k, recommendation_type, offset)
            
            # 批量查询推荐论文的详细信息
            placeholders = ','.join('?' * len(recommended_ids))
            details_query = f"""
                SELECT id, short_id, title, abstract, authors, journal, year, citation_count, topics, research_field
                FROM works 
                WHERE id IN ({placeholders})
            """
            
            async with db.execute(details_query, recommended_ids) as cursor:
                paper_details = await cursor.fetchall()
            
            # 创建ID到详情的映射
            details_map = {row[0]: row for row in paper_details}
            
            # 格式化推荐结果
            recommendations = []
            for i, paper_id in enumerate(recommended_ids):
                if paper_id in details_map:
                    row = details_map[paper_id]
                    short_id = row[1] or ''
                    title = row[2] or ''
                    abstract = row[3] or ''
                    authors = row[4] or ''
                    journal = row[5] or ''
                    year = row[6] or 0
                    citation_count = row[7] or 0
                    topics = row[8] or ''
                    research_field = row[9] or ''
                    
                    # 根据搜索排名计算相关性分数
                    relevance_score = max(0.1, 1.0 - (i * 0.01))  # 排名越靠前分数越高
                    
                    recommendations.append({
                        'paper_id': paper_id,  # 保留完整ID用于内部处理
                        'short_id': short_id,  # 添加短ID用于前端路由
                        'title': title,
                        'abstract': abstract,
                        'authors': authors,
                        'journal': journal,
                        'year': year,
                        'citation_count': citation_count,
                        'topics': topics,
                        'research_field': research_field,
                        'relevance_score': relevance_score,
                        'importance_score': min(1.0, (citation_count or 0) / 1000),
                        'recommendation_reason': f"{recommendation_type}基于向量相似度"
                    })
            
            logger.info(f"成功生成 {len(recommendations)} 条向量推荐")
            return recommendations[:top_k]
            
        except Exception as e:
            logger.error(f"生成推荐时出错: {str(e)}")
            return await self._get_popular_recommendations(db, top_k, f"{recommendation_type}异常")

    async def _get_paper_details(self, db: aiosqlite.Connection, paper_id: str) -> Optional[Dict[str, Any]]:
        """获取论文详细信息"""
        try:
            # 移除URL前缀获取短ID
            short_id = paper_id.replace('https://openalex.org/', '') if paper_id.startswith('https://') else paper_id
            
            query = """
                SELECT title, citation_count, year, journal, abstract
                FROM works 
                WHERE id = ?
            """
            
            async with db.execute(query, (short_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    title, citation_count, year, journal, abstract = row
                    
                    # 计算重要性分数
                    importance_score = min(1.0, (citation_count or 0) / 1000)
                    
                    return {
                        'title': title or 'Untitled',
                        'citation_count': citation_count or 0,
                        'year': year or 2020,
                        'journal': journal or '',
                        'abstract': abstract or '',
                        'importance_score': importance_score
                    }
            
        except Exception as e:
            logger.error(f"获取论文详情时出错 {paper_id}: {str(e)}")
            return None

    async def _get_popular_recommendations(self, db: aiosqlite.Connection, limit: int, recommendation_type: str, offset: int = 0) -> List[Dict[str, Any]]:
        """备用热门推荐"""
        try:
            query = """
                SELECT id, short_id, title, citation_count, year, journal
                FROM works 
                WHERE citation_count > 10 AND title IS NOT NULL AND title != ''
                ORDER BY citation_count DESC, year DESC
                LIMIT ? OFFSET ?
            """
            
            async with db.execute(query, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
            
            recommendations = []
            for row in rows:
                paper_id, short_id, title, citation_count, year, journal = row
                
                importance_score = min(1.0, (citation_count or 0) / 1000)
                
                recommendations.append({
                    'paper_id': paper_id,  # 保留完整ID用于内部处理
                    'short_id': short_id,  # 添加短ID用于前端路由
                    'title': title,
                    'relevance_score': 0.6,  # 基础相关性
                    'importance_score': importance_score,
                    'recommendation_reason': recommendation_type,
                    'citation_count': citation_count or 0,
                    'year': year or 2020,
                    'journal': journal or '',
                    'abstract': ''
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"获取热门推荐时出错: {str(e)}")
            return []

    async def _get_fallback_recommendations(self, limit: int, offset: int = 0) -> List[Dict[str, Any]]:
        """当向量服务不可用时的备用推荐"""
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                return await self._get_popular_recommendations(db, limit, "热门推荐", offset)
            finally:
                await db.close()
        except Exception as e:
            logger.error(f"获取备用推荐时出错: {str(e)}")
            return []

    def _is_available(self) -> bool:
        """检查推荐服务是否可用"""
        print(self.index)
        print(len(self.string_to_int_map))
        print(len(self.int_to_string_map))
        return (
            self.index is not None and 
            self.string_to_int_map and 
            self.int_to_string_map
        )

    async def get_popular_recommendations(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取热门推荐（兼容性方法）"""
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                return await self._get_popular_recommendations(db, limit, "热门推荐", offset)
            finally:
                await db.close()
        except Exception as e:
            logger.error(f"获取热门推荐时出错: {str(e)}")
            return []

    async def get_trending_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门主题（简化版）"""
        try:
            db = await aiosqlite.connect(self.db_path)
            try:
                query = """
                    SELECT 
                        CASE 
                            WHEN journal IS NOT NULL AND journal != '' THEN journal
                            ELSE '通用领域'
                        END as topic,
                        COUNT(*) as paper_count,
                        AVG(citation_count) as avg_citations
                    FROM works 
                    WHERE citation_count > 5
                    GROUP BY topic
                    HAVING paper_count > 10
                    ORDER BY avg_citations DESC, paper_count DESC
                    LIMIT ?
                """
                
                async with db.execute(query, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                
                topics = []
                for row in rows:
                    topic, paper_count, avg_citations = row
                    topics.append({
                        'topic': topic,
                        'paper_count': paper_count,
                        'avg_citations': round(avg_citations, 1) if avg_citations else 0,
                        'trend_score': min(100, int(avg_citations / 10)) if avg_citations else 0
                    })
                
                return topics
                
            finally:
                await db.close()
                
        except Exception as e:
            logger.error(f"获取热门主题时出错: {str(e)}")
            return []

