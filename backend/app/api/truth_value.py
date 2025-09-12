# backend/app/api/truth_value.py
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List
import os
import sqlite3
from pathlib import Path

router = APIRouter(prefix="/truth_value", tags=["truth-recommendations"])

TABLE_NAME = "ai_papers_scored"

def _resolve_db_path() -> str:
    env_path = os.getenv("TRUTH_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    here = Path(__file__).resolve()
    candidates: List[Path] = []
    try:
        candidates.append(here.parents[3] / "truth_value_calculation" / "openalex_5000_v1_graded.db")
    except Exception:
        pass
    candidates.append(Path(os.path.sep) / "article_recommendation_project" / "truth_value_calculation" / "openalex_5000_v1_graded.db")
    candidates.append(Path.cwd() / "truth_value_calculation" / "openalex_5000_v1_graded.db")
    candidates.append(Path.cwd() / "openalex_5000_v1_graded.db")

    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(
        "找不到真值数据库 openalex_5000_v1_graded.db。"
        " 可通过设置环境变量 TRUTH_DB_PATH=绝对路径 来指定。"
    )

DB_PATH = _resolve_db_path()

def _connect():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/")
def get_truth_recommendations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    try:
        conn = _connect()
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(1) FROM {TABLE_NAME} WHERE norm_score IS NOT NULL")
        total = int(cur.fetchone()[0])

        sql = f"""
            SELECT
                short_id AS id,
                short_id,
                title,
                authors,
                publication_year,
                journal,
                abstract,
                keywords,
                citation_count,
                fwci,
                norm_score
            FROM {TABLE_NAME}
            WHERE norm_score IS NOT NULL
            ORDER BY norm_score DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(sql, (limit, offset))
        rows = cur.fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            rec = dict(row)
            score = rec.get("norm_score") or 0.0
            try:
                score = float(score)
            except Exception:
                score = 0.0
            percent = round(score * 100.0, 1)
            rec["truth_value"] = score
            rec["truth_value_percent"] = percent
            rec["truth_value_text"] = f"{percent:.1f}分"
            # 前端用到的统一字段名（你的 types.ts 里有 year: number | string）
            rec["year"] = rec.pop("publication_year", None)
            items.append(rec)

        return {"items": items, "total": total}

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询真值推荐失败: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
