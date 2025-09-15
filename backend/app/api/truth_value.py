# backend/app/api/truth_value.py

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Tuple
import os
import sqlite3
from pathlib import Path

router = APIRouter(prefix="/truth_value", tags=["truth-recommendations"])

# 推理输出表（由 infer 脚本写入）
TRUTH_TABLE = "truth_agg_results"

# 用于补齐元信息的源表优先级（存在就用，按从左到右优先）
SOURCE_PREFERRED = [
    "forged_p0", "forged_p5", "forged_p10", "forged_p15",
    "forged_p20", "forged_p25", "forged_p35", "forged_p50", "forged_p70"
]

# ---- 路径解析：已设置环境变量 TRUTH_DB_PATH 时优先使用 ----
def _resolve_db_path() -> str:
    env_path = os.getenv("TRUTH_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    # 兜底：相对工程目录的几个常见位置
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
        if p.exists():
            return str(p)
    raise FileNotFoundError("找不到真值数据库。请设置环境变量 TRUTH_DB_PATH 指向包含 truth_agg_results 与源表的 SQLite。")

DB_PATH = _resolve_db_path()

def _connect():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _eligible_sources(conn: sqlite3.Connection) -> List[str]:
    return [t for t in SOURCE_PREFERRED if _table_exists(conn, t)]

def _build_metadata_index(conn: sqlite3.Connection, sids: List[str], sources: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    批量按 short_id 从多个源表补齐元信息。
    返回: { short_id: {title, authors, publication_year, journal, abstract, keywords, citation_count, fwci} }
    规则：按 sources 的优先顺序，取第一个非空值。
    """
    if not sids or not sources:
        return {}

    # 为了兼容 SQLite 参数数量限制，必要时分块
    CHUNK = 999
    meta: Dict[str, Dict[str, Any]] = {}

    # 需要的列
    cols = [
        "short_id", "title", "authors", "publication_year", "journal",
        "abstract", "keywords", "citation_count", "fwci"
    ]

    # 初始化结构
    for sid in sids:
        meta[sid] = {c: None for c in cols}

    # 按优先级依次填充
    for src in sources:
        # 构造 SQL
        base_sql = f"SELECT {', '.join(cols)} FROM {src} WHERE short_id IN ({{placeholders}})"
        # 分块执行
        for i in range(0, len(sids), CHUNK):
            chunk = sids[i:i+CHUNK]
            placeholders = ",".join(["?"] * len(chunk))
            sql = base_sql.format(placeholders=placeholders)
            cur = conn.execute(sql, chunk)
            for row in cur.fetchall():
                d = dict(row)
                sid = d.get("short_id")
                if not sid:
                    continue
                # 仅填充当前仍为空的字段
                dst = meta[sid]
                for k in cols:
                    if k == "short_id":
                        continue
                    if dst[k] in (None, "", 0) and d.get(k) not in (None, ""):
                        dst[k] = d.get(k)

    return meta


@router.get("/")
def get_truth_recommendations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """
    返回前端所需字段：
      - id/short_id/title/authors/year/journal/abstract/keywords/citation_count/fwci
      - truth_value, truth_value_percent, truth_value_text（百分制）
    逻辑：
      1) 先从 truth_agg_results 取推理出的字段（pred_* / abstract_text / keywords_text / truth_score_pct）
      2) 如有缺失，再按 short_id 到源表（按优先顺序）补齐
    """
    try:
        conn = _connect()
        cur = conn.cursor()

        if not _table_exists(conn, TRUTH_TABLE):
            # 没跑过推理：直接报错更明确
            raise HTTPException(status_code=500, detail=f"缺少表 {TRUTH_TABLE}，请先运行推理脚本生成真值。")

        # 统计总数
        cur.execute(f"SELECT COUNT(1) FROM {TRUTH_TABLE}")
        total = int(cur.fetchone()[0])

        # 主查询：仅读推理表（优先使用推理结果）
        sql = f"""
        SELECT
            short_id,
            pred_citations,
            pred_fwci,
            pred_year,
            abstract_text,
            keywords_text,
            truth_score_pct
        FROM {TRUTH_TABLE}
        ORDER BY COALESCE(truth_score_pct, 0) DESC
        LIMIT ? OFFSET ?;
        """
        cur.execute(sql, (limit, offset))
        base_rows = [dict(r) for r in cur.fetchall()]

        # 若没有任何行，直接返回空
        if not base_rows:
            return {"items": [], "total": 0}

        # 需要补齐元信息的 short_id 列表
        sids = [r["short_id"] for r in base_rows if r.get("short_id")]
        sources = _eligible_sources(conn)
        meta_index = _build_metadata_index(conn, sids, sources)

        items: List[Dict[str, Any]] = []
        for r in base_rows:
            sid = r["short_id"]
            meta = meta_index.get(sid, {}) if sid else {}

            # 基本字段：优先使用“推理结果”，缺了再用源表
            title   = meta.get("title") or ""
            authors = meta.get("authors") or ""
            journal = meta.get("journal") or ""
            # 年份/数值：推理 pred_* 优先，缺了才用源表
            pred_year_val = r.get("pred_year")
            if pred_year_val not in (None, ""):
                try:
                    year = int(round(float(pred_year_val)))  # ← 四舍五入到整年
                except Exception:
                    year = None
            else:
                year = meta.get("publication_year")

            # 如果还是字符串或浮点，尽量转成 int（避免前端出现小数或字符串）
            try:
                if year is not None and not isinstance(year, int):
                    year = int(round(float(year)))
            except Exception:
                pass

            cit = r.get("pred_citations") if r.get("pred_citations") not in (None, "") else meta.get("citation_count")
            fwci = r.get("pred_fwci") if r.get("pred_fwci") not in (None, "") else meta.get("fwci")

            # 文本：推理抽取的文本优先，缺了才用源表的原文
            abstract = r.get("abstract_text") if r.get("abstract_text") else (meta.get("abstract") or "")
            keywords = r.get("keywords_text") if r.get("keywords_text") else (meta.get("keywords") or "")

            # 分数：truth_score_pct（百分制）；如果没有，给 0（或你想回退到旧库的 norm_score，这里就查一次 ai_papers_scored）
            pct = r.get("truth_score_pct")
            if pct is None:
                score_percent = 0.0
            else:
                try:
                    score_percent = float(pct)
                except Exception:
                    score_percent = 0.0
            score01 = round(score_percent / 100.0, 4)

            item = {
                "id": sid,
                "short_id": sid,
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "abstract": abstract,
                "keywords": keywords,
                "citation_count": cit,
                "fwci": fwci,
                # 前端期望的三个字段
                "truth_value": score01,
                "truth_value_percent": round(score_percent, 1),
                "truth_value_text": f"{score_percent:.1f}分",
            }
            items.append(item)

        return {"items": items, "total": total}

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询真值推荐失败: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
