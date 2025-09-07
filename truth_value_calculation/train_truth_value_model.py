# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import math
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

FEATURE_NAMES = {
    "id": ["short_id"],
    "citations": ["citation_count"],
    "fwci": ["fwci"],
    "abstract": ["abstract"],
    "keywords": ["keywords"],
    "year": ["publication_year"],
    "label": ["norm_score"]
}

WORD_RE = re.compile(r"[A-Za-z]+|[\u4e00-\u9fa5]+|\d+")

def norm_id(row: Dict) -> Optional[str]:
    for k in FEATURE_NAMES["id"]:
        if k in row and pd.notna(row[k]):
            v = str(row[k]).strip()
            if v:
                return v
    return None

def select_best_table(conn: sqlite3.Connection) -> str:
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    if tables.empty:
        raise RuntimeError("No tables found in DB.")
    best_name = None
    best_score = -1
    for t in tables["name"].tolist():
        try:
            cols = pd.read_sql_query(f"PRAGMA table_info('{t}')", conn)["name"].str.lower().tolist()
        except Exception:
            continue
        score = 0
        for cat in ["id", "citations", "fwci", "abstract", "keywords", "year", "label"]:
            for c in FEATURE_NAMES[cat]:
                if c.lower() in cols:
                    score += 1
        if score > best_score:
            best_score = score
            best_name = t
    return best_name or tables["name"].iloc[0]

def pick_first_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set([c.lower() for c in df.columns])
    for c in candidates:
        if c.lower() in cols:
            return [col for col in df.columns if col.lower() == c.lower()][0]
    return None

def parse_abstract(val) -> str:
    if isinstance(val, dict):
        xs = []
        for w, pos in val.items():
            freq = len(pos) if isinstance(pos, list) else 1
            xs.extend([w] * max(1, freq))
        return " ".join(xs)
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    xs = []
                    for w, pos in d.items():
                        freq = len(pos) if isinstance(pos, list) else 1
                        xs.extend([w] * max(1, freq))
                    return " ".join(xs)
            except Exception:
                return s
        return s
    if pd.isna(val):
        return ""
    return str(val)

def parse_keywords(val) -> str:
    if isinstance(val, np.ndarray):
        val = val.tolist()

    if isinstance(val, (list, tuple)):
        out = []
        for item in val:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
            elif isinstance(item, dict):
                for k in ("display_name", "name", "keyword", "term", "text"):
                    if k in item and item[k]:
                        out.append(str(item[k]))
                        break
            else:
                s = str(item).strip()
                if s:
                    out.append(s)
        return " ".join(out)

    if isinstance(val, dict):
        out = []
        for _, v in val.items():
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
            elif isinstance(v, dict):
                for kk in ("display_name", "name", "keyword", "term", "text"):
                    if kk in v and v[kk]:
                        out.append(str(v[kk]))
                        break
            else:
                s = str(v).strip()
                if s:
                    out.append(s)
        return " ".join(out) if out else ""

    if isinstance(val, str):
        s = val.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                data = json.loads(s.replace("'", '"'))
                return parse_keywords(data)
            except Exception:
                pass
        return re.sub(r"[;,]", " ", s)
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    return str(val)

def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [tok.lower() for tok in WORD_RE.findall(text)]

def hash_bow(tokens: List[str], dim: int = 256) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    for w in tokens:
        h = int(hashlib.sha1(w.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h % 2 == 0) else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

def safe_float(x) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

@dataclass
class SourceFeatures:
    paper_id: str
    citations: Optional[float]
    fwci: Optional[float]
    year: Optional[float]
    abs_text: str
    kw_text: str
    available: bool


def load_source_from_db(db_path: str, expect_label: bool = False) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
    conn = sqlite3.connect(db_path)
    table = select_best_table(conn)
    df = pd.read_sql_query(f"SELECT * FROM '{table}';", conn)
    conn.close()

    for c in df.columns:
        if df[c].dtype == object:
            sample = df[c].dropna().astype(str).head(5).tolist()
            if any(s.strip().startswith(("{", "[")) for s in sample):
                try:
                    df[c] = df[c].apply(lambda v: json.loads(v) if isinstance(v, str) and v.strip().startswith(("{", "[")) else v)
                except Exception:
                    pass

    id_col = pick_first_column(df, FEATURE_NAMES["id"])
    if not id_col:
        raise RuntimeError(f"[{os.path.basename(db_path)}] cannot find id-like column in table {table}")

    df["_norm_id"] = df.apply(lambda r: norm_id({k: r.get(k, None) for k in df.columns}), axis=1)
    df = df[~df["_norm_id"].isna()].copy()

    cit_col = pick_first_column(df, FEATURE_NAMES["citations"])
    fwci_col = pick_first_column(df, FEATURE_NAMES["fwci"])
    abs_col = pick_first_column(df, FEATURE_NAMES["abstract"])
    kw_col  = pick_first_column(df, FEATURE_NAMES["keywords"])
    year_col= pick_first_column(df, FEATURE_NAMES["year"])

    feats = pd.DataFrame({
        "paper_id": df["_norm_id"].astype(str),
        "citations": df[cit_col] if cit_col else np.nan,
        "fwci": df[fwci_col] if fwci_col else np.nan,
        "year": df[year_col] if year_col else np.nan,
        "abs_raw": df[abs_col] if abs_col else "",
        "kw_raw": df[kw_col] if kw_col else ""
    })

    feats["abs_text"] = feats["abs_raw"].apply(parse_abstract)
    feats["kw_text"]  = feats["kw_raw"].apply(parse_keywords)
    feats = feats.drop(columns=["abs_raw", "kw_raw"])

    labels = None
    if expect_label:
        lab_col = pick_first_column(df, FEATURE_NAMES["label"])
        if lab_col:
            labels = pd.Series(df.set_index("_norm_id")[lab_col], name="label")

    return feats, labels

def attach_source_prefix(df: pd.DataFrame, db_path: str) -> pd.DataFrame:
    base = os.path.splitext(os.path.basename(db_path))[0]
    prefix = base
    rename_map = {}
    for c in ["citations", "fwci", "year", "abs_text", "kw_text"]:
        if c in df.columns:
            rename_map[c] = f"{prefix}_{c}"
    out = df.copy().rename(columns=rename_map)
    return out

def merge_sources(graded_df: pd.DataFrame, noisy_list: List[pd.DataFrame]) -> pd.DataFrame:
    ids = set(graded_df["paper_id"])
    dfs = []

    g = graded_df.copy()
    g = g[g["paper_id"].isin(ids)]
    g = g.rename(columns={
        "citations": "graded_citations",
        "fwci": "graded_fwci",
        "year": "graded_year",
        "abs_text": "graded_abs_text",
        "kw_text": "graded_kw_text"
    }).set_index("paper_id")
    dfs.append(g)

    for noisy_df in noisy_list:
        dfs.append(noisy_df.set_index("paper_id"))

    merged = dfs[0]
    for i, d in enumerate(dfs[1:], start=1):
        merged = merged.join(d, how="outer", rsuffix=f"__dup{i}")

    merged = merged.loc[list(ids)]
    return merged.reset_index()


@dataclass
class HashConfig:
    abs_dim: int = 256
    kw_dim: int = 128

@dataclass
class NumericStats:
    mean: float
    std: float

@dataclass
class FeatureStats:
    numeric: Dict[str, Dict[str, NumericStats]]
    hash: HashConfig
    sources_order: List[str]

def build_sources_order(columns: List[str]) -> List[str]:
    """严格按后缀识别源名，避免把 *_abs / *_kw 误识别成源。"""
    SUFFIXES = ["_citations", "_fwci", "_year", "_abs_text", "_kw_text"]
    srcs = set()
    for c in columns:
        for suf in SUFFIXES:
            if c.endswith(suf):
                srcs.add(c[: -len(suf)])
                break
    ordered = sorted([s for s in srcs if s != "graded"])
    return (["graded"] + ordered) if "graded" in srcs else ordered

def assemble_wide_frame(graded_db: str, noisy_dbs: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
    # graded: 带标签；noisy：不带标签
    graded_feats, labels = load_source_from_db(graded_db, expect_label=True)
    if labels is None:
        raise RuntimeError("Graded DB 未找到标签列（norm_score）。")

    noisy_feats_list = []
    for p in noisy_dbs:
        f, _ = load_source_from_db(p, expect_label=False)
        f = attach_source_prefix(f, p)
        noisy_feats_list.append(f)

    merged = merge_sources(graded_feats, noisy_feats_list)

    # 对齐标签
    y = labels.reindex(merged["paper_id"])
    y_vals = y.astype(float).values
    if np.any(np.isnan(y_vals)):
        raise RuntimeError("标签中存在 NaN，请检查 graded DB。")
    ymin, ymax = float(np.min(y_vals)), float(np.max(y_vals))
    if ymin < 0.0 or ymax > 1.0 or (ymax - ymin) > 1.0 + 1e-6:
        rng = max(1e-8, ymax - ymin)
        y = pd.Series((y_vals - ymin) / rng, index=y.index, name="label")
    return merged, y

def compute_numeric_stats(train_df: pd.DataFrame, sources: List[str]) -> Dict[str, Dict[str, NumericStats]]:
    stats: Dict[str, Dict[str, NumericStats]] = {}
    for s in sources:
        stats[s] = {}
        for n in ["citations", "fwci", "year"]:
            col = f"{s}_{n}"
            if col in train_df.columns:
                x = pd.to_numeric(train_df[col], errors="coerce").astype(float).values
                mask = np.isfinite(x)
                if mask.any():
                    mu = float(np.mean(x[mask]))
                    sd = float(np.std(x[mask]))
                    if not np.isfinite(sd) or sd < 1e-8:
                        sd = 1.0
                else:
                    mu, sd = 0.0, 1.0
                stats[s][n] = NumericStats(mu, sd)
            else:
                stats[s][n] = NumericStats(0.0, 1.0)
    return stats

def row_to_source_feature(row: pd.Series, source: str) -> SourceFeatures:
    def getv(name):
        c = f"{source}_{name}"
        return row[c] if c in row.index else np.nan
    citations = safe_float(getv("citations"))
    fwci = safe_float(getv("fwci"))
    year = safe_float(getv("year"))
    abs_text = str(getv("abs_text")) if pd.notna(getv("abs_text")) else ""
    kw_text  = str(getv("kw_text"))  if pd.notna(getv("kw_text"))  else ""
    available = any([citations is not None, fwci is not None, year is not None, bool(abs_text.strip()), bool(kw_text.strip())])
    return SourceFeatures(row["paper_id"], citations, fwci, year, abs_text, kw_text, available)

def vectorize_source(sf: SourceFeatures, source_name: str, stats: FeatureStats) -> Tuple[np.ndarray, int]:
    num_vec = []
    for n in ["citations", "fwci", "year"]:
        st = stats.numeric.get(source_name, {}).get(n, NumericStats(0.0, 1.0))
        val = getattr(sf, n)
        if val is None or not np.isfinite(val):
            z = 0.0
        else:
            if n == "citations":
                val = math.log1p(max(0.0, val))
            z = (val - st.mean) / (st.std if st.std > 0 else 1.0)
        num_vec.append(z)
    num_vec = np.array(num_vec, dtype=np.float32)

    abs_vec = hash_bow(tokenize(sf.abs_text), dim=stats.hash.abs_dim)
    kw_vec  = hash_bow(tokenize(sf.kw_text),  dim=stats.hash.kw_dim)
    full = np.concatenate([num_vec, abs_vec, kw_vec], axis=0)  # 3 + abs_dim + kw_dim
    mask = 1 if sf.available else 0
    return full, mask


class TruthDataset(Dataset):
    def __init__(self, df: pd.DataFrame, y: pd.Series, feature_stats: FeatureStats):
        self.sources = feature_stats.sources_order
        self.stats = feature_stats
        self.y = y.reindex(df["paper_id"]).astype(float).values.astype(np.float32)

        feats = []
        masks = []
        for _, row in df.reset_index(drop=True).iterrows():
            row_vecs = []
            row_masks = []
            for s in self.sources:
                sf = row_to_source_feature(row, s)
                v, m = vectorize_source(sf, s, self.stats)
                row_vecs.append(v)
                row_masks.append(m)
            feats.append(np.stack(row_vecs, axis=0))                 # [S,F]
            masks.append(np.array(row_masks, dtype=np.float32))      # [S]
        self.X = torch.from_numpy(np.stack(feats, axis=0)).float()   # [N,S,F]
        self.M = torch.from_numpy(np.stack(masks, axis=0)).float()   # [N,S]

    def __len__(self):
        return self.X.shape[0]

    def __getitem__(self, idx):
        return self.X[idx], self.M[idx], torch.tensor(self.y[idx], dtype=torch.float32)

class SourceEncoder(nn.Module):
    def __init__(self, in_dim: int, src_count: int, src_embed_dim: int = 16, hidden: int = 256, out_dim: int = 128, pdrop: float = 0.1):
        super().__init__()
        self.src_emb = nn.Embedding(src_count, src_embed_dim)
        self.mlp = nn.Sequential(
            nn.Linear(in_dim + src_embed_dim, hidden),
            nn.ReLU(inplace=True),
            nn.LayerNorm(hidden),
            nn.Dropout(pdrop),
            nn.Linear(hidden, out_dim),
            nn.ReLU(inplace=True),
            nn.LayerNorm(out_dim)
        )

    def forward(self, x: torch.Tensor, src_ids: torch.Tensor) -> torch.Tensor:
        B, S, F = x.shape
        if src_ids.dim() == 1:
            src_ids = src_ids.unsqueeze(0).expand(B, -1)
        src_e = self.src_emb(src_ids)
        z = torch.cat([x, src_e], dim=-1)
        out = self.mlp(z)
        return out

class TruthModel(nn.Module):
    def __init__(self, feature_dim: int, src_count: int, src_embed_dim: int = 16, enc_hidden=256, enc_out=128, head_hidden=64, pdrop=0.1):
        super().__init__()
        self.encoder = SourceEncoder(feature_dim, src_count, src_embed_dim, enc_hidden, enc_out, pdrop)
        self.head = nn.Sequential(
            nn.Linear(enc_out, head_hidden),
            nn.ReLU(inplace=True),
            nn.Dropout(pdrop),
            nn.Linear(head_hidden, 1)
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, X: torch.Tensor, M: torch.Tensor) -> torch.Tensor:
        """
        X: [B,S,F]  M: [B,S] (mask: 1有该源 0缺失)
        """
        B, S, F = X.shape
        src_ids = torch.arange(S, device=X.device).long()   # [S]
        H = self.encoder(X, src_ids)                        # [B,S,E]
        Mexp = M.unsqueeze(-1)                              # [B,S,1]
        denom = torch.clamp(Mexp.sum(dim=1), min=1.0)       # [B,1]
        pooled = (H * Mexp).sum(dim=1) / denom              # [B,E]
        yhat = self.sigmoid(self.head(pooled)).squeeze(-1)  # [B]
        return yhat


def split_train_valid_test(ids: List[str], ratios=(0.7, 0.15, 0.15)) -> Tuple[List[int], List[int], List[int]]:
    idx = list(range(len(ids)))
    random.Random(SEED).shuffle(idx)
    n = len(idx)
    n_tr = int(n * ratios[0])
    n_va = int(n * ratios[1])
    tr = idx[:n_tr]
    va = idx[n_tr:n_tr+n_va]
    te = idx[n_tr+n_va:]
    return tr, va, te

def rmse(pred, true):
    return float(torch.sqrt(torch.mean((pred - true) ** 2)).item())

def r2_score(pred, true):
    y_mean = torch.mean(true)
    ss_tot = torch.sum((true - y_mean) ** 2)
    ss_res = torch.sum((true - pred) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-12)
    return float(r2.item())

def train_loop(model, tr_loader, va_loader, epochs=30, lr=1e-3, device="cpu", patience=5):
    crit = nn.MSELoss()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    best_va = 1e9
    best_state = None
    wait = 0

    for ep in range(1, epochs + 1):
        model.train()
        tr_loss = 0.0
        for X, M, y in tr_loader:
            X = X.to(device=device, dtype=torch.float32)
            M = M.to(device=device, dtype=torch.float32)
            y = y.to(device=device, dtype=torch.float32)

            opt.zero_grad()
            yhat = model(X, M)
            loss = crit(yhat, y)
            loss.backward()
            opt.step()
            tr_loss += float(loss.item()) * X.size(0)
        tr_loss /= len(tr_loader.dataset)

        model.eval()
        va_loss = 0.0
        preds = []
        gts = []
        with torch.no_grad():
            for X, M, y in va_loader:
                X = X.to(device=device, dtype=torch.float32)
                M = M.to(device=device, dtype=torch.float32)
                y = y.to(device=device, dtype=torch.float32)
                yhat = model(X, M)
                loss = crit(yhat, y)
                va_loss += float(loss.item()) * X.size(0)
                preds.append(yhat.cpu())
                gts.append(y.cpu())
        va_loss /= len(va_loader.dataset)
        preds = torch.cat(preds, dim=0)
        gts = torch.cat(gts, dim=0)

        print(f"[Epoch {ep:03d}] train_loss={tr_loss:.5f} valid_loss={va_loss:.5f}  "
              f"valid_RMSE={rmse(preds,gts):.4f}  valid_R2={r2_score(preds,gts):.4f}")

        if va_loss < best_va - 1e-6:
            best_va = va_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                print(f"Early stopping at epoch {ep}. Best valid_loss={best_va:.5f}")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graded", type=str, default="openalex_5000_v1_graded.db")
    parser.add_argument("--noisy_dbs", type=str, nargs="+", default=[
        "openalex_5000_noisy3.db",
        "openalex_5000_noisy4.db",
        "openalex_5000_noisy5.db",
        "openalex_5000_noisy6.db",
        "openalex_5000_noisy7.db",
        "openalex_5000_noisy8.db",
        "openalex_5000_noisy9.db",
    ])
    parser.add_argument("--abs_dim", type=int, default=256)
    parser.add_argument("--kw_dim", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--patience", type=int, default=5)
    args = parser.parse_args()

    print("Loading and merging sources...")
    wide_df, y = assemble_wide_frame(args.graded, args.noisy_dbs)

    # 推断 8 个源
    cols = wide_df.columns.tolist()
    sources = build_sources_order(cols)
    print(f"Detected sources ({len(sources)}): {sources}")

    # 划分数据集
    ids = wide_df["paper_id"].tolist()
    tr_idx, va_idx, te_idx = split_train_valid_test(ids, ratios=(0.7, 0.15, 0.15))
    tr_df, va_df, te_df = wide_df.iloc[tr_idx].copy(), wide_df.iloc[va_idx].copy(), wide_df.iloc[te_idx].copy()
    y_tr, y_va, y_te = y.iloc[tr_idx].copy(), y.iloc[va_idx].copy(), y.iloc[te_idx].copy()

    # 保证每个源的 5 列都存在（缺失则填 NaN 占位）
    for s in sources:
        for n in ["citations", "fwci", "year", "abs_text", "kw_text"]:
            col = f"{s}_{n}"
            if col not in wide_df.columns:
                for df in (tr_df, va_df, te_df):
                    df[col] = np.nan

    num_stats = compute_numeric_stats(tr_df, sources)
    fstats = FeatureStats(
        numeric=num_stats,
        hash=HashConfig(abs_dim=args.abs_dim, kw_dim=args.kw_dim),
        sources_order=sources
    )

    train_ds = TruthDataset(tr_df, y_tr, fstats)
    valid_ds = TruthDataset(va_df, y_va, fstats)
    test_ds  = TruthDataset(te_df, y_te, fstats)

    tr_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=False)
    va_loader = DataLoader(valid_ds, batch_size=args.batch_size, shuffle=False, drop_last=False)
    te_loader = DataLoader(test_ds,  batch_size=args.batch_size, shuffle=False, drop_last=False)

    # 模型
    feature_dim = 3 + args.abs_dim + args.kw_dim   # per source
    model = TruthModel(feature_dim=feature_dim, src_count=len(sources)).to(args.device)

    print("Start training...")
    model = train_loop(model, tr_loader, va_loader, epochs=args.epochs, lr=args.lr,
                       device=args.device, patience=args.patience)

    # 测试集评估
    model.eval()
    preds = []
    gts = []
    with torch.no_grad():
        for X, M, yb in te_loader:
            X = X.to(device=args.device, dtype=torch.float32)
            M = M.to(device=args.device, dtype=torch.float32)
            yhat = model(X, M)
            preds.append(yhat.cpu())
            gts.append(yb.cpu())
    preds = torch.cat(preds, dim=0)
    gts = torch.cat(gts, dim=0)
    print(f"[TEST] RMSE={rmse(preds,gts):.4f}  R2={r2_score(preds,gts):.4f}")

    # 保存产物
    torch.save(model.state_dict(), "truthscore_model.pt")
    print("Saved model to truthscore_model.pt")

    serial_stats = {
        "numeric": {s: {n: {"mean": st.mean, "std": st.std} for n, st in d.items()} for s, d in num_stats.items()},
        "hash": {"abs_dim": args.abs_dim, "kw_dim": args.kw_dim},
        "sources_order": sources
    }
    with open("feature_stats.json", "w", encoding="utf-8") as f:
        json.dump(serial_stats, f, ensure_ascii=False, indent=2)
    print("Saved feature stats to feature_stats.json")

    cov = {}
    for s in sources:
        have = 0
        for _, row in wide_df.iterrows():
            has_any = False
            for n in ["citations", "fwci", "year", "abs_text", "kw_text"]:
                v = row.get(f"{s}_{n}", np.nan)
                if n in ["abs_text", "kw_text"]:
                    if isinstance(v, str) and v.strip():
                        has_any = True
                        break
                else:
                    if pd.notna(v):
                        has_any = True
                        break
            if has_any:
                have += 1
        cov[s] = {"available_rows": have, "total_rows": len(wide_df)}
    with open("id_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(cov, f, ensure_ascii=False, indent=2)
    print("Saved coverage report to id_coverage_report.json")

if __name__ == "__main__":
    try:
        import colorama
        colorama.just_fix_windows_console()
    except Exception:
        pass
    main()
