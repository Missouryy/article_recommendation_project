"""
真实数据库连接和操作模块 - 自动初始化版本
自动检测并创建缺失的表和索引
"""
import sqlite3
import aiosqlite
import json
import os
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from pathlib import Path
import logging
import math
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库文件路径（通过配置文件管理）
from .config import db_config
DB_PATH = db_config.get_database_path()

class DatabaseConnection:
    """数据库连接管理类"""
    
    def __init__(self):
        self.db_path = str(DB_PATH)
        self._initialized = False
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
    
    async def get_connection(self):
        """获取异步数据库连接 - 每次都创建新连接"""
        # 确保数据库已初始化
        if not self._initialized:
            await self._ensure_initialized()
        return await aiosqlite.connect(self.db_path)
    
    def get_sync_connection(self):
        """获取同步数据库连接"""
        # 确保数据库已初始化
        if not self._initialized:
            # 对于同步连接，我们需要在另一个线程中运行初始化
            import threading
            import asyncio
            
            def run_init():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._ensure_initialized())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_init)
            thread.start()
            thread.join()
        
        return sqlite3.connect(self.db_path)
    
    async def _ensure_initialized(self):
        """确保数据库已初始化"""
        if self._initialized:
            return
        
        try:
            # 导入数据库管理器
            from .database_manager import DatabaseManager
            
            # 创建数据库管理器并初始化
            db_manager = DatabaseManager(self.db_path)
            success = await db_manager.initialize_database()
            
            if success:
                logger.info("数据库自动初始化成功")
                self._initialized = True
            else:
                logger.error("数据库自动初始化失败")
                # 即使初始化失败，也继续运行，但记录错误
                
        except Exception as e:
            logger.error(f"数据库初始化过程中发生错误: {str(e)}")
            # 即使初始化失败，也继续运行，但记录错误

class RealDatabase:
    """真实数据库操作类"""
    
    def __init__(self):
        self.connection = DatabaseConnection()
        # 作者信息简单缓存，降低重复详情请求的计算与IO
        self._author_info_cache: Dict[str, Dict[str, Any]] = {}
        self._author_info_cache_ts: Dict[str, float] = {}
        self._author_info_cache_ttl_seconds: int = 1800  # 30分钟
    
    def _format_paper_data(self, row) -> Dict[str, Any]:
        """格式化论文数据"""
        if not row:
            return None
        
        # 解析JSON字段
        def safe_json_loads(value, default=None):
            if not value:
                return default or []
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default or []
        
        def safe_get(row, index, default=None):
            """安全获取行数据，避免索引越界"""
            try:
                return row[index] if row[index] is not None else default
            except (IndexError, TypeError):
                return default
        
        # 处理authors字段（可能是JSON字符串）
        authors_raw = safe_json_loads(safe_get(row, 3))
        authors = []
        if authors_raw:
            for author in authors_raw:
                if isinstance(author, dict) and 'author_id' in author:
                    authors.append(author['author_id'])
                elif isinstance(author, str):
                    authors.append(author)

        # 处理author_names字段（可能是JSON数组或以分号/逗号分隔的纯文本）
        author_names_value = safe_get(row, 4)
        author_names = safe_json_loads(author_names_value)
        if not author_names:
            # 当为纯文本时，尝试以分号或逗号拆分
            if isinstance(author_names_value, str) and author_names_value.strip():
                separator = ';' if ';' in author_names_value else ','
                author_names = [name.strip() for name in author_names_value.split(separator) if name and name.strip()]
            # 如果仍为空，回退从authors_raw中提取name
            if not author_names and authors_raw:
                extracted_names = []
                for author in authors_raw:
                    if isinstance(author, dict) and 'name' in author and author['name']:
                        extracted_names.append(str(author['name']).strip())
                    elif isinstance(author, str) and author.strip():
                        extracted_names.append(author.strip())
                author_names = extracted_names

        # 处理topics字段，确保返回字典列表
        topics_raw = safe_json_loads(safe_get(row, 26))  # topics列的正确索引
        topics = []
        if topics_raw:
            for topic in topics_raw:
                if isinstance(topic, str):
                    topics.append({"display_name": topic})
                elif isinstance(topic, dict):
                    topics.append(topic)
        
        return {
            "id": safe_get(row, 0, ""),
            "short_id": safe_get(row, 1),
            "title": safe_get(row, 2, ""),
            "authors": authors,
            "author_names": author_names,
            "year": safe_get(row, 5, 0),
            "journal": safe_get(row, 6, ""),
            "journal_impact_factor": None,  # 这个字段在数据库中不存在
            "abstract": safe_get(row, 7, ""),
            "keywords": safe_json_loads(safe_get(row, 8)),
            "doi": safe_get(row, 9, ""),
            "citation_count": safe_get(row, 10, 0),
            "download_count": safe_get(row, 11, 0),
            "created_at": safe_get(row, 24, ""),  # 使用publication_date
            "url": safe_get(row, 12, ""),
            "references": safe_json_loads(safe_get(row, 13)),
            "cited_by": [],  # cited_by在数据库中是INTEGER，不是列表
            "research_field": safe_get(row, 15, ""),
            "funding": safe_json_loads(safe_get(row, 16)),
            "journal_issn": safe_get(row, 17),
            "host_organization": safe_get(row, 18),
            "author_orcids": safe_json_loads(safe_get(row, 19)),
            "author_institutions": safe_json_loads(safe_get(row, 20)),
            "author_countries": safe_json_loads(safe_get(row, 21)),
            "fwci": safe_get(row, 22),
            "citation_percentile": safe_get(row, 23),
            "publication_date": safe_get(row, 24),
            "primary_topic": safe_get(row, 25),
            "topics": topics,
            "keywords_display": safe_get(row, 27),
            "domain": safe_get(row, 28),
            "truth_value_score": None
        }
    
    async def get_papers(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """获取论文列表"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT id, short_id, title, authors, author_names, year, journal, abstract, keywords, doi,
                       citation_count, download_count, url, reference_ids, cited_by, research_field, funding,
                       journal_issn, host_organization_name, author_orcids, author_institutions, author_countries,
                       fwci, citation_percentile, publication_date, primary_topic, topics, keywords_display, domain, crawl_timestamp
                FROM works 
                ORDER BY citation_count DESC 
                LIMIT ? OFFSET ?
            """
            async with db.execute(query, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
                return [self._format_paper_data(row) for row in rows if row]
        finally:
            await db.close()
    
    async def get_paper_by_id(self, paper_id: str) -> Dict[str, Any] | None:
        """通过ID或short_id获取论文详情"""
        db = await self.connection.get_connection()
        try:
            # 如果是short_id格式（如W2963095307），转换为完整ID查询
            if paper_id.startswith('W') and len(paper_id) <= 15:
                query = """
                    SELECT id, short_id, title, authors, author_names, year, journal, abstract, keywords, doi,
                           citation_count, download_count, url, reference_ids, cited_by, research_field, funding,
                           journal_issn, host_organization_name, author_orcids, author_institutions, author_countries,
                           fwci, citation_percentile, publication_date, primary_topic, topics, keywords_display, domain, crawl_timestamp
                    FROM works 
                    WHERE short_id = ?
                """
                async with db.execute(query, (paper_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return self._format_paper_data(row)
            else:
                # 如果是完整ID，直接查询
                query = """
                    SELECT id, short_id, title, authors, author_names, year, journal, abstract, keywords, doi,
                           citation_count, download_count, url, reference_ids, cited_by, research_field, funding,
                           journal_issn, host_organization_name, author_orcids, author_institutions, author_countries,
                           fwci, citation_percentile, publication_date, primary_topic, topics, keywords_display, domain, crawl_timestamp
                    FROM works 
                    WHERE id = ?
                """
                async with db.execute(query, (paper_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return self._format_paper_data(row)
            return None
        finally:
            await db.close()
    
    async def search_papers(self, query: str, filters: Dict = None) -> List[Dict[str, Any]]:
        """搜索论文：加权混合相关度（标题/作者/关键词/摘要/期刊等）"""
        db = await self.connection.get_connection()
        try:
            query_normalized = (query or "").strip().lower()
            if not query_normalized:
                return []

            # 将查询拆分为词元（空格切分），用于更广的候选召回
            tokens = [t for t in query_normalized.split() if t]
            like_params: List[str] = []

            # 动态构造 WHERE 子句：对每个 token 在多个字段 OR 匹配
            fields = [
                "LOWER(title)",
                "LOWER(abstract)",
                "LOWER(author_names)",  # JSON字符串，低成本LIKE
                "LOWER(keywords)",      # JSON字符串，低成本LIKE
                "LOWER(journal)"
            ]

            where_clauses: List[str] = []
            if tokens:
                for token in tokens:
                    token_like = f"%{token}%"
                    # 为该token构造 (field1 LIKE ? OR field2 LIKE ? ...)
                    token_sub = " OR ".join(f"{f} LIKE ?" for f in fields)
                    where_clauses.append(f"({token_sub})")
                    like_params.extend([token_like] * len(fields))
            else:
                # 兜底：使用整句
                token_like = f"%{query_normalized}%"
                token_sub = " OR ".join(f"{f} LIKE ?" for f in fields)
                where_clauses.append(f"({token_sub})")
                like_params.extend([token_like] * len(fields))

            where_sql = " OR ".join(where_clauses)

            sql = f"""
                SELECT id, short_id, title, authors, author_names, year, journal, abstract, keywords, doi,
                       citation_count, download_count, url, reference_ids, cited_by, research_field, funding,
                       journal_issn, host_organization_name, author_orcids, author_institutions, author_countries,
                       fwci, citation_percentile, publication_date, primary_topic, topics, keywords_display, domain, crawl_timestamp
                FROM works 
                WHERE {where_sql}
                ORDER BY citation_count DESC
                LIMIT 500
            """

            async with db.execute(sql, like_params) as cursor:
                rows = await cursor.fetchall()

            # 计算加权相关度
            results: List[Dict[str, Any]] = []
            full_phrase = query_normalized
            for row in rows:
                paper = self._format_paper_data(row)
                if not paper:
                    continue

                title_text = (paper.get("title") or "").lower()
                abstract_text = (paper.get("abstract") or "").lower()
                journal_text = (paper.get("journal") or "").lower()
                author_names_list = paper.get("author_names") or []
                keywords_list = paper.get("keywords") or []
                author_text = " ".join([a.lower() for a in author_names_list])
                keywords_text = " ".join([k.lower() for k in keywords_list])

                relevance_score: float = 0.0

                # token 逐字段加权
                for token in tokens if tokens else [full_phrase]:
                    if token in title_text:
                        relevance_score += 3.0
                    if token in author_text:
                        relevance_score += 2.0
                    if token in keywords_text:
                        relevance_score += 2.5
                    if token in abstract_text:
                        relevance_score += 1.5
                    if token in journal_text:
                        relevance_score += 1.0

                # 短语匹配加分
                if full_phrase and full_phrase in title_text:
                    relevance_score += 3.0
                if full_phrase and full_phrase in abstract_text:
                    relevance_score += 2.0
                if full_phrase and full_phrase in keywords_text:
                    relevance_score += 2.0

                # 时效性与影响力
                current_year = datetime.now().year
                year_value = paper.get("year") or 0
                if isinstance(year_value, int) and year_value > 0:
                    years_old = max(0, current_year - year_value)
                    recency_bonus = max(0.0, 2.0 - years_old * 0.2)
                    relevance_score += recency_bonus

                citation_count = paper.get("citation_count") or 0
                try:
                    citation_bonus = min(2.0, math.log(citation_count + 1) * 0.5)
                except ValueError:
                    citation_bonus = 0.0
                relevance_score += citation_bonus

                if relevance_score <= 0:
                    # 保留极少数完全未匹配的候选为0分（通常不会发生）
                    continue

                paper["relevance_score"] = round(relevance_score, 4)
                results.append(paper)

            # 应用过滤（在结果层做，避免过早过滤导致召回不足）
            if filters:
                results = self._apply_filters(results, filters)

            return results
        finally:
            await db.close()

    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """在已召回结果上应用过滤条件（与API层保持一致的语义）"""
        filtered_results = list(results)

        # 年份过滤
        if filters.get("year_min") is not None:
            filtered_results = [r for r in filtered_results if (r.get("year") or 0) >= filters["year_min"]]
        if filters.get("year_max") is not None:
            filtered_results = [r for r in filtered_results if (r.get("year") or 0) <= filters["year_max"]]

        # 期刊过滤
        if filters.get("journals"):
            journal_names = {str(j).lower() for j in filters["journals"]}
            filtered_results = [r for r in filtered_results if (r.get("journal") or "").lower() in journal_names]

        # 研究领域过滤
        if filters.get("research_fields"):
            field_names = {str(f).lower() for f in filters["research_fields"]}
            filtered_results = [r for r in filtered_results if (r.get("research_field") or "").lower() in field_names]

        # 最小引用数
        if filters.get("min_citations") is not None:
            filtered_results = [r for r in filtered_results if (r.get("citation_count") or 0) >= filters["min_citations"]]

        # 最小真值分数
        if filters.get("min_truth_value") is not None:
            filtered_results = [r for r in filtered_results if (r.get("truth_value_score") or 0) >= filters["min_truth_value"]]

        # 作者过滤（按名称）
        if filters.get("authors"):
            author_names = {str(a).lower() for a in filters["authors"]}
            filtered_results = [
                r for r in filtered_results
                if any((str(author).lower() in author_names) for author in (r.get("author_names") or []))
            ]

        return filtered_results
    
    async def get_papers_by_author(self, author_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """根据作者姓名获取论文"""
        db = await self.connection.get_connection()
        try:
            search_pattern = f"%{author_name.lower()}%"
            query = """
                SELECT id, short_id, title, authors, author_names, year, journal, abstract, keywords, doi,
                       citation_count, download_count, url, reference_ids, cited_by, research_field, funding,
                       journal_issn, host_organization_name, author_orcids, author_institutions, author_countries,
                       fwci, citation_percentile, publication_date, primary_topic, topics, keywords_display, domain, crawl_timestamp
                FROM works 
                WHERE LOWER(author_names) LIKE ?
                ORDER BY citation_count DESC 
                LIMIT ?
            """
            async with db.execute(query, (search_pattern, limit)) as cursor:
                rows = await cursor.fetchall()
                return [self._format_paper_data(row) for row in rows if row]
        finally:
            await db.close()
    
    async def get_author_info(self, author_name: str) -> Dict[str, Any] | None:
        """获取作者信息（通过聚合论文数据计算）"""
        # 先查缓存
        try:
            cached = self._author_info_cache.get(author_name)
            ts = self._author_info_cache_ts.get(author_name, 0)
            if cached and (time.time() - ts) < self._author_info_cache_ttl_seconds:
                return cached
        except Exception:
            pass

        # 读取部分（最多300篇）即可得到稳定的统计且更快
        papers = await self.get_papers_by_author(author_name, limit=300)
        
        if not papers:
            return None
        
        # 计算统计信息
        total_citations = sum(paper.get("citation_count", 0) for paper in papers)
        total_papers = len(papers)
        
        # 计算h-index
        citations = sorted([paper.get("citation_count", 0) for paper in papers], reverse=True)
        h_index = 0
        for i, citation_count in enumerate(citations):
            if citation_count >= i + 1:
                h_index = i + 1
            else:
                break
        
        # 提取研究领域（频次统计）和机构信息
        from collections import Counter
        field_counter: Counter[str] = Counter()
        generic_fields = {
            "mathematics", "geometry", "geodesy", "geography", "philosophy", "epistemology",
            "scaling", "linear scale", "simple (philosophy)", "spin (aerodynamics)", "physics"
        }
        def is_valid_field(name: str) -> bool:
            n = (name or "").strip()
            if len(n) < 3 or len(n) > 80:
                return False
            return n.lower() not in generic_fields
        def within_word_limit(s: str) -> bool:
            return len([w for w in s.split() if w]) <= 5
        affiliations = set()
        
        for paper in papers:
            if paper.get("research_field"):
                name = str(paper["research_field"]).strip()
                if name and is_valid_field(name):
                    field_counter[name] += 1
            institutions = paper.get("author_institutions", [])
            if institutions:
                for inst in institutions:
                    if isinstance(inst, str):
                        affiliations.add(inst)
            # 兼容 primary_topic 和 topics.display_name
            if paper.get("primary_topic"):
                name = str(paper["primary_topic"]).strip()
                if name and is_valid_field(name):
                    field_counter[name] += 1
            for t in (paper.get("topics") or []):
                name = t.get("display_name") if isinstance(t, dict) else None
                level = t.get("level") if isinstance(t, dict) else None
                if isinstance(name, str):
                    clean = name.strip()
                    if clean and is_valid_field(clean) and isinstance(level, int) and level >= 1:
                        field_counter[clean] += 1
        
        # 选择出现频次最高的前5个研究领域，且每个不超过5个单词
        top_fields = [n for n, _ in field_counter.most_common(20) if within_word_limit(n)][:5]

        affiliation_str = "、".join(list(affiliations)[:3]) if affiliations else ""
        result = {
            "id": author_name.replace(' ', '_'),
            "name": author_name,
            "affiliation": affiliation_str,
            "research_areas": top_fields,
            "h_index": h_index,
            "citation_count": total_citations,
            "paper_count": total_papers,
            "created_at": datetime.now().isoformat(),
            "career_timeline": [],
            "collaboration_network": []
        }

        # 写入缓存
        try:
            self._author_info_cache[author_name] = result
            self._author_info_cache_ts[author_name] = time.time()
        except Exception:
            pass
        return result
    
    async def get_research_fields_stats(self) -> Dict[str, Any]:
        """获取研究领域统计"""
        db = await self.connection.get_connection()
        try:
            # 获取前20个最活跃的研究领域
            query = """
                SELECT research_field, COUNT(*) as paper_count, SUM(citation_count) as total_citations
                FROM works 
                WHERE research_field IS NOT NULL AND research_field != ''
                GROUP BY research_field 
                ORDER BY paper_count DESC 
                LIMIT 20
            """
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return {
                    "field_distribution": {row[0]: {"papers": row[1], "citations": row[2]} for row in rows}
                }
        finally:
            await db.close()
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        db = await self.connection.get_connection()
        try:
            # 总论文数
            total_query = "SELECT COUNT(*) FROM works"
            async with db.execute(total_query) as cursor:
                total_papers = (await cursor.fetchone())[0]
            
            # 年份分布统计
            year_query = """
                SELECT year, COUNT(*) 
                FROM works 
                WHERE year IS NOT NULL 
                GROUP BY year 
                ORDER BY year DESC 
                LIMIT 10
            """
            async with db.execute(year_query) as cursor:
                year_stats = await cursor.fetchall()
            
            return {
                "total_papers": total_papers,
                "year_distribution": {str(year): count for year, count in year_stats}
            }
        finally:
            await db.close()


class UserManager:
    """用户数据管理（使用SQLite数据库）"""
    
    def __init__(self):
        self.connection = DatabaseConnection()
    
    async def get_user_by_username(self, username: str) -> Dict[str, Any] | None:
        """根据用户名获取用户"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT * FROM users WHERE username = ?"
            async with db.execute(query, (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._format_user_data(row)
                return None
        finally:
            await db.close()
    
    async def get_user_by_email(self, email: str) -> Dict[str, Any] | None:
        """根据邮箱获取用户"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT * FROM users WHERE email = ?"
            async with db.execute(query, (email,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._format_user_data(row)
                return None
        finally:
            await db.close()
    
    async def get_user_by_id(self, user_id: str) -> Dict[str, Any] | None:
        """根据ID获取用户"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT * FROM users WHERE id = ?"
            async with db.execute(query, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._format_user_data(row)
                return None
        finally:
            await db.close()
    
    async def get_user_count(self) -> int:
        """获取用户总数"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT COUNT(*) FROM users"
            async with db.execute(query) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        finally:
            await db.close()
    
    async def get_users(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户列表"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?"
            async with db.execute(query, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
                users = []
                for row in rows:
                    user_data = self._format_user_data(row)
                    if user_data:
                        users.append(user_data)
                return users
        finally:
            await db.close()
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户"""
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # 处理研究兴趣（转为JSON字符串）
        research_interests = json.dumps(user_data.get("research_interests", []))
        
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT INTO users (id, username, email, password_hash, full_name, 
                                 affiliation, research_interests, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            values = (
                user_id,
                user_data["username"],
                user_data["email"],
                user_data["password_hash"],
                user_data.get("full_name"),
                user_data.get("affiliation"),
                research_interests,
                created_at,
                created_at
            )
            await db.execute(query, values)
            await db.commit()
            
            # 返回创建的用户数据
            return await self.get_user_by_id(user_id)
        finally:
            await db.close()
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any] | None:
        """更新用户信息"""
        db = await self.connection.get_connection()
        try:
            # 构建更新查询
            update_fields = []
            values = []
            
            for field, value in update_data.items():
                if field == "research_interests" and isinstance(value, list):
                    value = json.dumps(value)
                update_fields.append(f"{field} = ?")
                values.append(value)
            
            if not update_fields:
                return await self.get_user_by_id(user_id)
            
            # 添加更新时间
            update_fields.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(user_id)
            
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
            await db.execute(query, values)
            await db.commit()
            
            return await self.get_user_by_id(user_id)
        finally:
            await db.close()
    
    async def update_last_login(self, user_id: str):
        """更新最后登录时间"""
        await self.update_user(user_id, {"last_login": datetime.now().isoformat()})
    
    # 收藏管理
    async def add_bookmark(self, user_id: str, paper_id: str) -> bool:
        """添加论文收藏"""
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT OR IGNORE INTO user_bookmarks (user_id, paper_id, created_at)
                VALUES (?, ?, ?)
            """
            await db.execute(query, (user_id, paper_id, datetime.now().isoformat()))
            await db.commit()
            return True
        except Exception:
            return False
        finally:
            await db.close()
    
    async def remove_bookmark(self, user_id: str, paper_id: str) -> bool:
        """移除论文收藏"""
        db = await self.connection.get_connection()
        try:
            query = "DELETE FROM user_bookmarks WHERE user_id = ? AND paper_id = ?"
            cursor = await db.execute(query, (user_id, paper_id))
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()
    
    async def get_user_bookmarks(self, user_id: str) -> List[str]:
        """获取用户收藏的论文ID列表"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT paper_id FROM user_bookmarks 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """
            async with db.execute(query, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        finally:
            await db.close()
    
    async def is_bookmarked(self, user_id: str, paper_id: str) -> bool:
        """检查论文是否已收藏"""
        db = await self.connection.get_connection()
        try:
            query = "SELECT 1 FROM user_bookmarks WHERE user_id = ? AND paper_id = ?"
            async with db.execute(query, (user_id, paper_id)) as cursor:
                row = await cursor.fetchone()
                return row is not None
        finally:
            await db.close()
    
    # 关注管理
    async def follow_author(self, user_id: str, author_id: str) -> bool:
        """关注作者"""
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT OR IGNORE INTO user_follows (user_id, author_id, created_at)
                VALUES (?, ?, ?)
            """
            await db.execute(query, (user_id, author_id, datetime.now().isoformat()))
            await db.commit()
            return True
        except Exception:
            return False
        finally:
            await db.close()
    
    async def unfollow_author(self, user_id: str, author_id: str) -> bool:
        """取消关注作者"""
        db = await self.connection.get_connection()
        try:
            query = "DELETE FROM user_follows WHERE user_id = ? AND author_id = ?"
            cursor = await db.execute(query, (user_id, author_id))
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()
    
    async def get_followed_authors(self, user_id: str) -> List[str]:
        """获取关注的作者ID列表"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT author_id FROM user_follows 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """
            async with db.execute(query, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        finally:
            await db.close()
    
    # 阅读历史
    async def add_reading_history(self, user_id: str, paper_id: str):
        """添加阅读历史"""
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT INTO user_reading_history (user_id, paper_id, created_at)
                VALUES (?, ?, ?)
            """
            await db.execute(query, (user_id, paper_id, datetime.now().isoformat()))
            await db.commit()
        finally:
            await db.close()
    
    async def get_reading_history(self, user_id: str, limit: int = 50) -> List[str]:
        """获取阅读历史"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT DISTINCT paper_id FROM user_reading_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """
            async with db.execute(query, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        finally:
            await db.close()
    
    # 搜索历史
    async def add_search_history(self, user_id: str, query: str):
        """添加搜索历史"""
        db = await self.connection.get_connection()
        try:
            insert_query = """
                INSERT INTO user_search_history (user_id, query, created_at)
                VALUES (?, ?, ?)
            """
            await db.execute(insert_query, (user_id, query, datetime.now().isoformat()))
            await db.commit()
        finally:
            await db.close()
    
    async def get_search_history(self, user_id: str, limit: int = 20) -> List[str]:
        """获取搜索历史"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT DISTINCT query FROM user_search_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """
            async with db.execute(query, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        finally:
            await db.close()
    
    async def clear_search_history(self, user_id: str) -> bool:
        """清除用户的搜索历史"""
        db = await self.connection.get_connection()
        try:
            query = "DELETE FROM user_search_history WHERE user_id = ?"
            cursor = await db.execute(query, (user_id,))
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()
    
    # 收藏夹管理
    async def create_folder(self, user_id: str, folder_data: Dict[str, Any]) -> Dict[str, Any] | None:
        """创建收藏夹"""
        folder_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT INTO user_folders (id, user_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            await db.execute(query, (
                folder_id, user_id, folder_data["name"],
                folder_data.get("description"), created_at, created_at
            ))
            await db.commit()
            
            return {
                "id": folder_id,
                "name": folder_data["name"],
                "description": folder_data.get("description"),
                "created_at": created_at,
                "updated_at": created_at,
                "paper_count": 0
            }
        finally:
            await db.close()
    
    async def get_user_folders(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的收藏夹列表"""
        db = await self.connection.get_connection()
        try:
            query = """
                SELECT uf.*, COUNT(fp.paper_id) as paper_count
                FROM user_folders uf
                LEFT JOIN folder_papers fp ON uf.id = fp.folder_id
                WHERE uf.user_id = ?
                GROUP BY uf.id
                ORDER BY uf.created_at DESC
            """
            async with db.execute(query, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                folders = []
                for row in rows:
                    folders.append({
                        "id": row[0],
                        "user_id": row[1],
                        "name": row[2],
                        "description": row[3],
                        "created_at": row[4],
                        "updated_at": row[5],
                        "paper_count": row[6]
                    })
                return folders
        finally:
            await db.close()
    
    async def add_paper_to_folder(self, folder_id: str, paper_id: str) -> bool:
        """将论文添加到收藏夹"""
        db = await self.connection.get_connection()
        try:
            query = """
                INSERT OR IGNORE INTO folder_papers (folder_id, paper_id, added_at)
                VALUES (?, ?, ?)
            """
            await db.execute(query, (folder_id, paper_id, datetime.now().isoformat()))
            await db.commit()
            return True
        except Exception:
            return False
        finally:
            await db.close()
    
    async def remove_paper_from_folder(self, folder_id: str, paper_id: str) -> bool:
        """从收藏夹移除论文"""
        db = await self.connection.get_connection()
        try:
            query = "DELETE FROM folder_papers WHERE folder_id = ? AND paper_id = ?"
            cursor = await db.execute(query, (folder_id, paper_id))
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()
    
    async def delete_folder(self, folder_id: str, user_id: str) -> bool:
        """删除收藏夹"""
        db = await self.connection.get_connection()
        try:
            # 先删除收藏夹中的论文
            await db.execute("DELETE FROM folder_papers WHERE folder_id = ?", (folder_id,))
            # 再删除收藏夹
            cursor = await db.execute(
                "DELETE FROM user_folders WHERE id = ? AND user_id = ?", 
                (folder_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()
    
    def _format_user_data(self, row) -> Dict[str, Any]:
        """格式化用户数据"""
        if not row:
            return None
            
        # 解析研究兴趣JSON
        try:
            research_interests = json.loads(row[6]) if row[6] else []
        except (json.JSONDecodeError, TypeError):
            research_interests = []
        
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "password_hash": row[3],
            "full_name": row[4],
            "affiliation": row[5],
            "research_interests": research_interests,
            "created_at": row[7],
            "last_login": row[8],
            "updated_at": row[9] if len(row) > 9 else None
        }


# 全局数据库实例
db = RealDatabase()
user_manager = UserManager()

# 数据库管理相关方法
async def get_database_info():
    """获取数据库信息"""
    try:
        from .database_manager import DatabaseManager
        db_manager = DatabaseManager(str(DB_PATH))
        return db_manager.get_database_info()
    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        return {"error": str(e)}

async def check_database_health():
    """检查数据库健康状态"""
    try:
        from .database_manager import DatabaseManager
        db_manager = DatabaseManager(str(DB_PATH))
        return await db_manager.check_database_health()
    except Exception as e:
        logger.error(f"检查数据库健康状态失败: {str(e)}")
        return {"error": str(e)}

async def initialize_database():
    """手动初始化数据库"""
    try:
        from .database_manager import DatabaseManager
        db_manager = DatabaseManager(str(DB_PATH))
        return await db_manager.initialize_database()
    except Exception as e:
        logger.error(f"手动初始化数据库失败: {str(e)}")
        return False
