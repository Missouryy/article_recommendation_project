import aiosqlite
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class AuthorDatabase:
    """作者库（author_db.db）访问模块。"""

    def __init__(self):
        # 解析项目根目录并定位 author_db.db
        here = Path(__file__).resolve()
        candidates = [
            here.parents[3] / "author_db.db",
            Path.cwd() / "author_db.db",
        ]
        db_path: Optional[Path] = None
        for p in candidates:
            try:
                if p.exists():
                    db_path = p
                    break
            except Exception:
                continue
        if db_path is None:
            # 不抛出异常，留给上层在调用时处理 None 结果
            self.db_path = None
        else:
            self.db_path = str(db_path)

    async def get_connection(self):
        if not self.db_path:
            raise FileNotFoundError("未找到 author_db.db，请确保其位于项目根目录")
        return await aiosqlite.connect(self.db_path)

    def get_sync_connection(self):
        if not self.db_path:
            raise FileNotFoundError("未找到 author_db.db，请确保其位于项目根目录")
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _row_to_summary(row) -> Dict[str, Any]:
        # 列顺序参考 crawler/author_crawler.py 中的建表语句
        openalex_id = row[0]
        display_name = row[1] or ""
        institution = row[3] or ""
        research_areas_str = row[4] or ""
        cited_by_count = row[5] or 0
        works_count = row[6] or 0
        research_areas = [s.strip() for s in research_areas_str.split(",") if s and s.strip()]
        return {
            "id": display_name.replace(" ", "_"),  # 前端沿用 name 作为路由 id
            "name": display_name,
            "affiliation": institution,
            "research_areas": research_areas[:5],
            "h_index": 0,  # 无法从作者库直接计算
            "citation_count": int(cited_by_count),
            "paper_count": int(works_count),
        }

    @staticmethod
    def _row_to_detail(row) -> Dict[str, Any]:
        openalex_id = row[0]
        display_name = row[1] or ""
        institution = row[3] or ""
        research_areas_str = row[4] or ""
        cited_by_count = row[5] or 0
        works_count = row[6] or 0
        first_year = row[7]
        last_year = row[8]
        research_areas = [s.strip() for s in research_areas_str.split(",") if s and s.strip()]
        return {
            "id": display_name.replace(" ", "_"),
            "name": display_name,
            "affiliation": institution,
            "research_areas": research_areas[:5],
            "h_index": 0,
            "citation_count": int(cited_by_count),
            "paper_count": int(works_count),
            "created_at": datetime.now().isoformat(),
            "career_timeline": [],
            "collaboration_network": [],
        }

    async def search_authors(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not query:
            return []
        db = await self.get_connection()
        try:
            like = f"%{query.lower()}%"
            sql = (
                "SELECT openalex_id, display_name, orcid, institution, research_areas, "
                "cited_by_count, works_count, first_publication_year, last_publication_year "
                "FROM authors WHERE LOWER(display_name) LIKE ? ORDER BY cited_by_count DESC LIMIT ?"
            )
            async with db.execute(sql, (like, limit)) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_summary(r) for r in rows or []]
        finally:
            await db.close()

    async def get_popular_authors(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        db = await self.get_connection()
        try:
            sql = (
                "SELECT openalex_id, display_name, orcid, institution, research_areas, "
                "cited_by_count, works_count, first_publication_year, last_publication_year "
                "FROM authors ORDER BY cited_by_count DESC, works_count DESC LIMIT ? OFFSET ?"
            )
            async with db.execute(sql, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_summary(r) for r in rows or []]
        finally:
            await db.close()

    async def get_author_by_name(self, display_name: str) -> Optional[Dict[str, Any]]:
        if not display_name:
            return None
        db = await self.get_connection()
        try:
            sql = (
                "SELECT openalex_id, display_name, orcid, institution, research_areas, "
                "cited_by_count, works_count, first_publication_year, last_publication_year "
                "FROM authors WHERE display_name = ? LIMIT 1"
            )
            async with db.execute(sql, (display_name,)) as cursor:
                row = await cursor.fetchone()
            return self._row_to_detail(row) if row else None
        finally:
            await db.close()

    async def get_author_by_openalex_id(self, openalex_id: str) -> Optional[Dict[str, Any]]:
        if not openalex_id:
            return None
        db = await self.get_connection()
        try:
            sql = (
                "SELECT openalex_id, display_name, orcid, institution, research_areas, "
                "cited_by_count, works_count, first_publication_year, last_publication_year "
                "FROM authors WHERE openalex_id = ? LIMIT 1"
            )
            async with db.execute(sql, (openalex_id,)) as cursor:
                row = await cursor.fetchone()
            return self._row_to_detail(row) if row else None
        finally:
            await db.close()


# 全局实例
author_db = AuthorDatabase()
