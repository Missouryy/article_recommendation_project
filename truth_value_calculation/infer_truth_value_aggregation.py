# -*- coding: utf-8 -*-
"""
Inference for Truth-Value Aggregation (numeric + text) + percent truth score

- 输入：合并库（九源，多源缺失也可） + 训练好的 .pt 模型
- 输出：在同一 SQLite 新建/更新 truth_agg_results 表，包含：
    * pred_citations / pred_fwci / pred_year
    * abstract_top_source / abstract_text
    * keywords_top_source / keywords_text
    * weights_json_*（各任务权重，便于审计）
    * truth_score_pct（百分制真值分数，带一位小数）
"""

import argparse
import json
import os
import re
import sqlite3
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.feature_extraction.text import HashingVectorizer
from pathlib import Path

# -----------------------------
# 基本配置
# -----------------------------
THIS_DIR = Path(__file__).resolve().parent

DEFAULT_MERGED_DB = str((THIS_DIR / "data" / "forged_output_merged_v2.db").as_posix())
DEFAULT_MODEL = str((THIS_DIR / "truth_agg_text_model.pt").as_posix())

DEFAULT_SOURCES = [
    "forged_p0", "forged_p5", "forged_p10", "forged_p15", "forged_p20",
    "forged_p25", "forged_p35", "forged_p50", "forged_p70"
]
TASKS = ["citations", "fwci", "year", "abstract", "keywords"]
WORD_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fa5]+", re.U)

# 百分制总分的权重（可按需调整；默认等权）
WEIGHTS = {
    "citations": 1.0,
    "fwci": 1.0,
    "year": 1.0,
    "abstract": 1.0,   # 用 max weight 作为文本置信度
    "keywords": 1.0,   # 用 max weight 作为文本置信度
}


# -----------------------------
# DB 工具
# -----------------------------
def connect_db(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"DB not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

def read_table_to_map(conn: sqlite3.Connection, table: str) -> Dict[str, dict]:
    """按 short_id 读整表为 dict。"""
    if not table_exists(conn, table):
        return {}
    cur = conn.execute(f"SELECT * FROM {table}")
    data = {}
    for row in cur.fetchall():
        d = dict(row)
        sid = d.get("short_id")
        if sid:
            data[sid] = d
    return data

def ensure_result_table(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS truth_agg_results (
        short_id TEXT PRIMARY KEY,
        pred_citations REAL,
        pred_fwci REAL,
        pred_year REAL,
        abstract_top_source TEXT,
        abstract_text TEXT,
        keywords_top_source TEXT,
        keywords_text TEXT,
        weights_json_citations TEXT,
        weights_json_fwci TEXT,
        weights_json_year TEXT,
        weights_json_abstract TEXT,
        weights_json_keywords TEXT,
        truth_score_pct REAL
    );
    """)
    conn.commit()


# -----------------------------
# 嵌入（HashingVectorizer，无需拟合）
# -----------------------------
class SharedHV:
    _hv: Optional[HashingVectorizer] = None
    _dim: int = 512

    @classmethod
    def init(cls, dim: int):
        if cls._hv is None or cls._dim != dim:
            cls._hv = HashingVectorizer(
                n_features=dim,
                analyzer=lambda s: WORD_RE.findall(s.lower()),
                alternate_sign=False,
                norm='l2'
            )
            cls._dim = dim

    @classmethod
    def embed(cls, text: str) -> np.ndarray:
        hv = cls._hv
        assert hv is not None
        return hv.transform([text or ""]).toarray().astype(np.float32)[0]


def parse_keywords(kw_field: str) -> str:
    if not kw_field:
        return ""
    s = kw_field.strip()
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        inner = s[1:-1]
        parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
        return " ".join([p for p in parts if p])
    for delim in [";", ",", "|", "，", "；"]:
        if delim in s:
            parts = [p.strip() for p in s.split(delim)]
            return " ".join([p for p in parts if p])
    return s


# -----------------------------
# 任务特征构建
# -----------------------------
def to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def build_numeric_group(rows_by_source: List[Tuple[int, dict]], task: str, num_sources: int):
    """返回 feat_mat(S,18), x_arr(S,), src_idx_list"""
    xs = []
    src_idx_list = []
    for sidx, row in rows_by_source:
        if task == "citations":
            x = to_float(row.get("citation_count"))
        elif task == "fwci":
            x = to_float(row.get("fwci"))
        else:
            x = to_float(row.get("publication_year"))
        if x is None or (isinstance(x, float) and np.isnan(x)):
            continue
        xs.append(float(x))
        src_idx_list.append(sidx)
    if len(xs) == 0:
        return None, None, None

    values = np.array(xs, dtype=np.float32)
    mu = float(np.mean(values))
    med = float(np.median(values))
    std = float(np.std(values)) if len(values) > 1 else 0.0
    if std < 1e-12: std = 0.0

    feat_rows = []
    for x, sidx in zip(values, src_idx_list):
        src_oh = np.zeros(num_sources, dtype=np.float32); src_oh[sidx] = 1.0
        num_feats = np.array([x - med, x - mu, (x - mu)/std if std>0 else 0.0, 1.0], dtype=np.float32)
        t_oh = np.zeros(5, dtype=np.float32)
        t_oh[["citations","fwci","year","abstract","keywords"].index(task)] = 1.0
        feat = np.concatenate([src_oh, num_feats, t_oh], axis=0)
        feat_rows.append(feat)

    feat_mat = np.stack(feat_rows, axis=0).astype(np.float32)
    x_arr = values
    return feat_mat, x_arr, src_idx_list

def build_text_group(rows_by_source: List[Tuple[int, dict]], task: str, num_sources: int, emb_dim: int):
    """返回 feat_mat(S,18), emb_list(S,D), src_idx_list, texts(list[str])"""
    assert task in ("abstract","keywords")
    proxies = []
    embeds = []
    src_idx_list = []
    texts = []

    for sidx, row in rows_by_source:
        if task == "abstract":
            txt = (row.get("abstract") or "").strip()
            emb = SharedHV.embed(txt)
        else:
            txt = parse_keywords(row.get("keywords") or "")
            emb = SharedHV.embed(txt)
        embeds.append(emb.astype(np.float32))
        proxy = float(np.linalg.norm(emb))  # 稳定代理
        proxies.append(proxy)
        src_idx_list.append(sidx)
        texts.append(txt)

    if len(embeds) == 0:
        return None, None, None, None

    proxies = np.array(proxies, dtype=np.float32)
    mu = float(np.mean(proxies))
    med = float(np.median(proxies))
    std = float(np.std(proxies)) if len(proxies) > 1 else 0.0
    if std < 1e-12: std = 0.0

    feat_rows = []
    for proxy, sidx in zip(proxies, src_idx_list):
        src_oh = np.zeros(num_sources, dtype=np.float32); src_oh[sidx] = 1.0
        num_feats = np.array([proxy - med, proxy - mu, (proxy - mu)/std if std>0 else 0.0, 1.0], dtype=np.float32)
        t_oh = np.zeros(5, dtype=np.float32)
        t_oh[["citations","fwci","year","abstract","keywords"].index(task)] = 1.0
        feat = np.concatenate([src_oh, num_feats, t_oh], axis=0)
        feat_rows.append(feat)

    feat_mat = np.stack(feat_rows, axis=0).astype(np.float32)
    emb_list = np.stack(embeds, axis=0).astype(np.float32)
    return feat_mat, emb_list, src_idx_list, texts


# -----------------------------
# 模型（与训练保持一致）
# -----------------------------
class WeightNet(nn.Module):
    def __init__(self, in_dim=18, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, 1)
        )
    def forward_weights(self, feat_mat: torch.Tensor) -> torch.Tensor:
        return self.net(feat_mat)[:, 0]


# -----------------------------
# 参考分布（分位数）用于归一化
# -----------------------------
def collect_reference_quantiles(conn: sqlite3.Connection, sources: List[str]):
    """
    优先使用 p0 表的分布；若 p0 不存在，则合并所有存在源的分布。
    返回：{task: (q01, q99)}
    """
    def fetch_vals(table: str, col: str) -> List[float]:
        if not table_exists(conn, table): return []
        cur = conn.execute(f"SELECT {col} FROM {table}")
        vals = []
        for (v,) in cur.fetchall():
            try:
                if v is None: continue
                vals.append(float(v))
            except Exception:
                continue
        return vals

    def quantiles_from(vals: List[float]) -> Tuple[float, float]:
        if len(vals) == 0:
            return (0.0, 1.0)
        v = np.array(vals, dtype=np.float64)
        q01 = float(np.percentile(v, 1))
        q99 = float(np.percentile(v, 99))
        if q99 <= q01:
            q01, q99 = float(np.min(v)), float(np.max(v))
            if q99 <= q01:
                q01, q99 = 0.0, 1.0
        return q01, q99

    # 尝试 p0
    p0 = "forged_p0"
    refs = {}
    if p0 in sources and table_exists(conn, p0):
        refs["citations"] = quantiles_from(fetch_vals(p0, "citation_count"))
        refs["fwci"] = quantiles_from(fetch_vals(p0, "fwci"))
        refs["year"] = quantiles_from(fetch_vals(p0, "publication_year"))
    else:
        # 合并所有源
        all_cit, all_fwci, all_year = [], [], []
        for t in sources:
            all_cit += fetch_vals(t, "citation_count")
            all_fwci += fetch_vals(t, "fwci")
            all_year += fetch_vals(t, "publication_year")
        refs["citations"] = quantiles_from(all_cit)
        refs["fwci"] = quantiles_from(all_fwci)
        refs["year"] = quantiles_from(all_year)

    return refs  # dict: task -> (q01, q99)


def minmax_clip_norm(x: float, q01: float, q99: float) -> float:
    """分位数截断后的 Min–Max 归一化到 [0,1]"""
    if q99 <= q01:
        return 0.5
    xx = min(max(x, q01), q99)
    return (xx - q01) / (q99 - q01)


# -----------------------------
# 单篇推理 + 真值分数
# -----------------------------
@torch.no_grad()
def infer_one_paper(model: WeightNet,
                    source_maps: List[Dict[str, dict]],
                    sid: str,
                    device,
                    emb_dim: int,
                    source_names: List[str],
                    refs_quant: Dict[str, Tuple[float, float]]):
    """
    返回结果字典，含 truth_score_pct。
    """
    num_sources = len(source_maps)
    res = {
        "short_id": sid,
        "pred_citations": None,
        "pred_fwci": None,
        "pred_year": None,
        "abstract_top_source": None,
        "abstract_text": None,
        "keywords_top_source": None,
        "keywords_text": None,
        "weights_json_citations": None,
        "weights_json_fwci": None,
        "weights_json_year": None,
        "weights_json_abstract": None,
        "weights_json_keywords": None,
        "truth_score_pct": None,
    }

    # 收集存在该 short_id 的源行
    rows_by_source = []
    for sidx, smap in enumerate(source_maps):
        row = smap.get(sid)
        if row is not None:
            rows_by_source.append((sidx, row))
    if len(rows_by_source) == 0:
        return res  # 没有任何源就跳过

    # ---------- 数值任务 ----------
    norm_scores = {}  # 保存 0-1 的各项得分
    for task, outkey, wkey in [
        ("citations", "pred_citations", "weights_json_citations"),
        ("fwci", "pred_fwci", "weights_json_fwci"),
        ("year", "pred_year", "weights_json_year"),
    ]:
        feat_mat, x_arr, src_idx_list = build_numeric_group(rows_by_source, task, num_sources)
        if feat_mat is None:
            continue
        fm = torch.from_numpy(feat_mat).to(device)
        xa = torch.from_numpy(x_arr).to(device)
        logits = model.forward_weights(fm)
        w = torch.softmax(logits, dim=0)  # (S,)

        y_hat = float(torch.sum(w * xa).cpu().item())
        res[outkey] = y_hat

        # 归一化
        q01, q99 = refs_quant.get(task, (0.0, 1.0))
        norm_scores[task] = minmax_clip_norm(y_hat, q01, q99)

        # 权重 JSON（审计）
        w_np = w.cpu().numpy().tolist()
        res[wkey] = json.dumps([
            {"source": source_names[sidx], "weight": float(wt)}
            for sidx, wt in zip(src_idx_list, w_np)
        ], ensure_ascii=False)

    # ---------- 文本任务 ----------
    text_scores = {}
    for task, out_src_key, out_text_key, wkey in [
        ("abstract", "abstract_top_source", "abstract_text", "weights_json_abstract"),
        ("keywords", "keywords_top_source", "keywords_text", "weights_json_keywords"),
    ]:
        feat_mat, emb_list, src_idx_list, texts = build_text_group(rows_by_source, task, num_sources, emb_dim)
        if feat_mat is None:
            continue
        fm = torch.from_numpy(feat_mat).to(device)
        logits = model.forward_weights(fm)
        w = torch.softmax(logits, dim=0)  # (S,)

        # 文本“代表”：取权重最大的源文本
        top = int(torch.argmax(w).item())
        top_src_idx = src_idx_list[top]
        res[out_src_key] = source_names[top_src_idx]
        res[out_text_key] = texts[top]

        # 文本置信度得分：max weight ∈ [0,1]
        text_scores[task] = float(w[top].cpu().item())

        # 权重 JSON
        w_np = w.cpu().numpy().tolist()
        res[wkey] = json.dumps([
            {"source": source_names[sidx], "weight": float(wt)}
            for sidx, wt in zip(src_idx_list, w_np)
        ], ensure_ascii=False)

    # ---------- 汇总百分制分数 ----------
    # 缺失项自动忽略（只对存在的项做加权平均）
    parts = []
    weights = []
    for k in ["citations", "fwci", "year"]:
        if k in norm_scores:
            parts.append(norm_scores[k]); weights.append(WEIGHTS[k])
    for k in ["abstract", "keywords"]:
        if k in text_scores:
            parts.append(text_scores[k]); weights.append(WEIGHTS[k])

    if len(parts) > 0:
        wsum = sum(weights) if sum(weights) > 0 else 1.0
        score01 = float(np.dot(parts, weights) / wsum)   # 0-1
        res["truth_score_pct"] = round(score01 * 100.0, 1)
    else:
        res["truth_score_pct"] = None

    return res


# -----------------------------
# 主流程
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_db", type=str, default=DEFAULT_MERGED_DB)
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL)
    ap.add_argument("--sources", type=str, nargs="*", default=DEFAULT_SOURCES,
                    help="source table names in order; subset allowed")
    ap.add_argument("--emb_dim", type=int, default=512)
    ap.add_argument("--hidden", type=int, default=64, help="must match training")
    ap.add_argument("--batch", type=int, default=512, help="commit every N rows")
    args = ap.parse_args()

    # 嵌入初始化
    SharedHV.init(args.emb_dim)

    # 加载模型
    ckpt = torch.load(args.model, map_location="cpu")
    hidden = args.hidden
    model = WeightNet(in_dim=18, hidden=hidden)
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    # 连接 DB
    conn = connect_db(args.merged_db)
    ensure_result_table(conn)

    # 源表数据
    source_maps: List[Dict[str, dict]] = []
    for t in args.sources:
        m = read_table_to_map(conn, t)
        if len(m) == 0:
            print(f"[warn] source table '{t}' not found or empty.")
        source_maps.append(m)

    # 参考分位数（用于归一化到 0-1）
    refs_quant = collect_reference_quantiles(conn, args.sources)
    print("[refs] quantiles:", refs_quant)

    # 所有 short_id 的并集
    all_ids = set()
    for m in source_maps:
        all_ids.update(m.keys())
    all_ids = list(all_ids)
    print(f"Total papers found across sources: {len(all_ids)}")

    # 推理 & 落库
    cur = conn.cursor()
    cnt = 0
    for sid in all_ids:
        res = infer_one_paper(model, source_maps, sid, device, args.emb_dim, args.sources, refs_quant)
        cur.execute("""
            INSERT INTO truth_agg_results (
                short_id, pred_citations, pred_fwci, pred_year,
                abstract_top_source, abstract_text,
                keywords_top_source, keywords_text,
                weights_json_citations, weights_json_fwci, weights_json_year,
                weights_json_abstract, weights_json_keywords,
                truth_score_pct
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(short_id) DO UPDATE SET
              pred_citations=excluded.pred_citations,
              pred_fwci=excluded.pred_fwci,
              pred_year=excluded.pred_year,
              abstract_top_source=excluded.abstract_top_source,
              abstract_text=excluded.abstract_text,
              keywords_top_source=excluded.keywords_top_source,
              keywords_text=excluded.keywords_text,
              weights_json_citations=excluded.weights_json_citations,
              weights_json_fwci=excluded.weights_json_fwci,
              weights_json_year=excluded.weights_json_year,
              weights_json_abstract=excluded.weights_json_abstract,
              weights_json_keywords=excluded.weights_json_keywords,
              truth_score_pct=excluded.truth_score_pct
        """, (
            res["short_id"], res["pred_citations"], res["pred_fwci"], res["pred_year"],
            res["abstract_top_source"], res["abstract_text"],
            res["keywords_top_source"], res["keywords_text"],
            res["weights_json_citations"], res["weights_json_fwci"], res["weights_json_year"],
            res["weights_json_abstract"], res["weights_json_keywords"],
            res["truth_score_pct"]
        ))
        cnt += 1
        if cnt % args.batch == 0:
            conn.commit()
    conn.commit()
    print(f"Done. Wrote {cnt} rows into table truth_agg_results in {args.merged_db}")
    conn.close()


if __name__ == "__main__":
    main()
