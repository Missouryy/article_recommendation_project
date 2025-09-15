# -*- coding: utf-8 -*-
"""
Truth-Value Aggregation Training (numeric + text with embeddings)

- 多源：9 个源表（默认 forged_p0, forged_p5, ..., forged_p70）
- 任务：5 个（citations, fwci, year, abstract, keywords）
- 输入：每源 18 维 = 9(源 one-hot) + 4(Δmedian, Δmean, zscore, bias) + 5(任务 one-hot)
- 数值任务：softmax 权重 * 源数值 -> 聚合真值，对 p0 数值做 MSE
- 文本任务：HashingVectorizer embedding -> softmax 权重 * 各源向量 -> 聚合向量，对 p0 向量做 L2/MSE

输出：
- 训练日志、验证指标（数值 RMSE、文本余弦），保存最佳模型到 truth_agg_text_model.pt
"""

import argparse
import os
import sqlite3
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from sklearn.feature_extraction.text import HashingVectorizer
import re
from pathlib import Path

# -----------------------------
# 配置
# -----------------------------
THIS_DIR = Path(__file__).resolve().parent

DEFAULT_MERGED_DB = str((THIS_DIR / "data" / "forged_output_merged_v2.db").as_posix())
DEFAULT_GRADED_DB = str((THIS_DIR / "data" / "openalex_1000_graded.db").as_posix())


SOURCE_TABLES = [
    "forged_p0", "forged_p5", "forged_p10", "forged_p15", "forged_p20",
    "forged_p25", "forged_p35", "forged_p50", "forged_p70"
]
TASKS = ["citations", "fwci", "year", "abstract", "keywords"]

NUM_SOURCES = len(SOURCE_TABLES)
NUM_TASKS = len(TASKS)
FEAT_DIM = NUM_SOURCES + 4 + NUM_TASKS  # 18
WORD_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fa5]+", re.U)


# -----------------------------
# 工具函数
# -----------------------------
def connect_db(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"DB not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def parse_keywords(kw_field: str) -> str:
    if not kw_field:
        return ""
    s = str(kw_field).strip()
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
# 文本嵌入（HashingVectorizer，无需拟合、可复现）
# -----------------------------
class SharedHV:
    _hv: Optional[HashingVectorizer] = None
    _dim: int = 512

    @classmethod
    def init(cls, dim: int):
        if cls._hv is None or cls._dim != dim:
            cls._hv = HashingVectorizer(
                n_features=dim,
                analyzer=lambda s: WORD_RE.findall((s or "").lower()),
                alternate_sign=False,
                norm='l2'
            )
            cls._dim = dim

    @classmethod
    def embed(cls, text: str) -> np.ndarray:
        hv = cls._hv
        assert hv is not None, "HashingVectorizer not initialized. Call SharedHV.init(dim) first."
        return hv.transform([text or ""]).toarray().astype(np.float32)[0]


# -----------------------------
# 读取表为 map
# -----------------------------
def read_table_to_map(conn: sqlite3.Connection, table: str) -> Dict[str, dict]:
    cur = conn.execute(f"SELECT * FROM {table}")
    data = {}
    for row in cur.fetchall():
        d = dict(row)
        sid = d.get("short_id")
        if sid:
            data[sid] = d
    return data


# -----------------------------
# 数据集构建
# -----------------------------
def gather_samples(merged_db: str, graded_db: str, emb_dim: int):
    """
    返回 samples: List[dict]
    - 数值任务样本：
      {"is_text": False, "short_id", "task",
       "feat_mat": (S,18) float32, "x_arr": (S,) float32, "y_true": float}
    - 文本任务样本：
      {"is_text": True, "short_id", "task",
       "feat_mat": (S,18) float32, "emb_list": (S,D) float32, "emb_true": (D,) float32}
    """
    conn_m = connect_db(merged_db)
    conn_g = connect_db(graded_db)

    # 各源表
    src_maps: Dict[str, Dict[str, dict]] = {}
    for t in SOURCE_TABLES:
        src_maps[t] = read_table_to_map(conn_m, t)

    # 监督真值来源：graded 的 forged_p0
    graded_map = read_table_to_map(conn_g, "forged_p0")

    task_index = {t: i for i, t in enumerate(TASKS)}
    source_index = {t: i for i, t in enumerate(SOURCE_TABLES)}

    samples = []

    for sid, g_row in graded_map.items():
        # p0 作为真值
        gt_cit = to_float(g_row.get("citation_count"))
        gt_fwci = to_float(g_row.get("fwci"))
        gt_year = to_float(g_row.get("publication_year"))
        gt_abs = SharedHV.embed(g_row.get("abstract") or "")
        gt_kw = SharedHV.embed(parse_keywords(g_row.get("keywords") or ""))

        # ------- 数值任务：citations / fwci / year -------
        for task in ["citations", "fwci", "year"]:
            xs = []
            src_idx_list = []
            # 收集该论文在 9 源上的观测
            for sname, smap in src_maps.items():
                row = smap.get(sid)
                if not row:
                    continue
                if task == "citations":
                    x = to_float(row.get("citation_count"))
                    y_true = gt_cit
                elif task == "fwci":
                    x = to_float(row.get("fwci"))
                    y_true = gt_fwci
                else:
                    x = to_float(row.get("publication_year"))
                    y_true = gt_year
                if x is None or y_true is None:
                    continue
                xs.append(float(x))
                src_idx_list.append(source_index[sname])

            if len(xs) == 0:
                continue

            values = np.asarray(xs, dtype=np.float32)
            mu = float(np.mean(values))
            med = float(np.median(values))
            std = float(np.std(values)) if len(values) > 1 else 0.0
            if std < 1e-12: std = 0.0

            feat_rows = []
            for x, sidx in zip(values, src_idx_list):
                src_oh = np.zeros(NUM_SOURCES, dtype=np.float32); src_oh[sidx] = 1.0
                dif_med = x - med
                dif_mu = x - mu
                z = (x - mu) / std if std > 0 else 0.0
                num_feats = np.array([dif_med, dif_mu, z, 1.0], dtype=np.float32)
                t_oh = np.zeros(NUM_TASKS, dtype=np.float32); t_oh[task_index[task]] = 1.0
                feat = np.concatenate([src_oh, num_feats, t_oh], axis=0)  # 18
                feat_rows.append(feat)

            feat_mat = np.stack(feat_rows, axis=0).astype(np.float32)
            samples.append({
                "is_text": False,
                "short_id": sid,
                "task": task,
                "feat_mat": feat_mat,             # (S,18)
                "x_arr": values,                  # (S,)
                "y_true": float(y_true),          # scalar
            })

        # ------- 文本任务：abstract / keywords -------
        for task in ["abstract", "keywords"]:
            emb_list = []
            proxies = []
            src_idx_list = []
            for sname, smap in src_maps.items():
                row = smap.get(sid)
                if not row:
                    continue
                if task == "abstract":
                    txt = row.get("abstract") or ""
                else:
                    txt = parse_keywords(row.get("keywords") or "")
                emb = SharedHV.embed(txt)  # (D,) L2 normalized
                emb_list.append(emb.astype(np.float32))
                proxies.append(float(np.linalg.norm(emb)))  # 归一后一般接近 1，空文本是 0
                src_idx_list.append(source_index[sname])

            if len(emb_list) == 0:
                continue

            proxies = np.asarray(proxies, dtype=np.float32)
            mu = float(np.mean(proxies))
            med = float(np.median(proxies))
            std = float(np.std(proxies)) if len(proxies) > 1 else 0.0
            if std < 1e-12: std = 0.0

            feat_rows = []
            for proxy, sidx in zip(proxies, src_idx_list):
                src_oh = np.zeros(NUM_SOURCES, dtype=np.float32); src_oh[sidx] = 1.0
                dif_med = proxy - med
                dif_mu = proxy - mu
                z = (proxy - mu) / std if std > 0 else 0.0
                num_feats = np.array([dif_med, dif_mu, z, 1.0], dtype=np.float32)
                t_oh = np.zeros(NUM_TASKS, dtype=np.float32); t_oh[task_index[task]] = 1.0
                feat = np.concatenate([src_oh, num_feats, t_oh], axis=0)
                feat_rows.append(feat)

            feat_mat = np.stack(feat_rows, axis=0).astype(np.float32)
            emb_list = np.stack(emb_list, axis=0).astype(np.float32)

            emb_true = gt_abs if task == "abstract" else gt_kw  # (D,)
            samples.append({
                "is_text": True,
                "short_id": sid,
                "task": task,
                "feat_mat": feat_mat,      # (S,18)
                "emb_list": emb_list,      # (S,D)
                "emb_true": emb_true.astype(np.float32),  # (D,)
            })

    conn_m.close()
    conn_g.close()
    return samples


# -----------------------------
# Torch Dataset / Collate
# -----------------------------
class TruthAggDataset(Dataset):
    def __init__(self, samples: List[dict]):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        if not s["is_text"]:
            return (
                torch.from_numpy(s["feat_mat"]),      # (S,18)
                torch.from_numpy(s["x_arr"]),         # (S,)
                torch.tensor([s["y_true"]], dtype=torch.float32),  # (1,)
                torch.tensor(0, dtype=torch.long),    # is_text flag = 0
            )
        else:
            return (
                torch.from_numpy(s["feat_mat"]),      # (S,18)
                torch.from_numpy(s["emb_list"]),      # (S,D)
                torch.from_numpy(s["emb_true"]),      # (D,)
                torch.tensor(1, dtype=torch.long),    # is_text flag = 1
            )

def collate_variable(batch):
    """为可变 S 的样本准备批处理"""
    feat_list, carrier1, carrier2, is_text_flags = [], [], [], []
    for a, b, c, tflag in batch:
        feat_list.append(a)
        carrier1.append(b)   # x_arr 或 emb_list
        carrier2.append(c)   # y_true 或 emb_true
        is_text_flags.append(tflag)
    return feat_list, carrier1, carrier2, torch.stack(is_text_flags, dim=0)


# -----------------------------
# 模型：每源 18 维 -> 1 个 logit，再 softmax 得权重
# -----------------------------
class WeightNet(nn.Module):
    def __init__(self, in_dim=FEAT_DIM, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, 1)
        )

    def forward_weights(self, feat_mat: torch.Tensor) -> torch.Tensor:
        # feat_mat: (S,18) -> logits: (S,)
        return self.net(feat_mat)[:, 0]


# -----------------------------
# 训练 / 验证
# -----------------------------
def train_one_epoch(model, loader, opt, device, alpha_num=1.0, alpha_text=1.0):
    model.train()
    total_loss = 0.0
    num_batches = 0
    for feat_list, carrier1, carrier2, is_text_flags in loader:
        opt.zero_grad()
        loss_sum = 0.0
        for i in range(len(feat_list)):
            feat = feat_list[i].to(device)  # (S,18)
            logits = model.forward_weights(feat)
            w = torch.softmax(logits, dim=0)  # (S,)

            if is_text_flags[i].item() == 0:
                # 数值任务
                x_arr = carrier1[i].to(device)        # (S,)
                y_true = carrier2[i].to(device).squeeze(0)  # (1,) -> scalar
                y_hat = torch.sum(w * x_arr)
                loss_sum = loss_sum + alpha_num * (y_hat - y_true) ** 2
            else:
                # 文本任务
                emb_list = carrier1[i].to(device)     # (S,D)
                emb_true = carrier2[i].to(device)     # (D,)
                e_hat = torch.sum(w.unsqueeze(1) * emb_list, dim=0)  # (D,)
                loss_sum = loss_sum + alpha_text * torch.sum((e_hat - emb_true) ** 2)

        loss = loss_sum / max(1, len(feat_list))
        loss.backward()
        opt.step()
        total_loss += loss.item()
        num_batches += 1

    return total_loss / max(1, num_batches)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    # 数值：RMSE
    se_sum = 0.0
    n_num = 0
    # 文本：余弦相似度
    cos_list = []
    for feat_list, carrier1, carrier2, is_text_flags in loader:
        for i in range(len(feat_list)):
            feat = feat_list[i].to(device)
            logits = model.forward_weights(feat)
            w = torch.softmax(logits, dim=0)

            if is_text_flags[i].item() == 0:
                x_arr = carrier1[i].to(device)
                y_true = carrier2[i].to(device).squeeze(0)
                y_hat = torch.sum(w * x_arr)
                se_sum += float((y_hat - y_true) ** 2)
                n_num += 1
            else:
                emb_list = carrier1[i].to(device)
                emb_true = carrier2[i].to(device)
                e_hat = torch.sum(w.unsqueeze(1) * emb_list, dim=0)
                num = torch.dot(e_hat, emb_true)
                den = torch.norm(e_hat) * torch.norm(emb_true) + 1e-12
                cos = float(num / den)
                cos_list.append(cos)

    rmse = np.sqrt(se_sum / n_num) if n_num > 0 else None
    cos_mean = float(np.mean(cos_list)) if len(cos_list) > 0 else None
    return rmse, cos_mean, n_num, len(cos_list)


# -----------------------------
# 主函数
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_db", type=str, default=DEFAULT_MERGED_DB)
    ap.add_argument("--graded_db", type=str, default=DEFAULT_GRADED_DB)
    ap.add_argument("--emb_dim", type=int, default=512)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch_size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train_ratio", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--alpha_num", type=float, default=1.0, help="权重：数值 MSE")
    ap.add_argument("--alpha_text", type=float, default=1.0, help="权重：文本向量 MSE")
    args = ap.parse_args()

    # 初始化
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    SharedHV.init(args.emb_dim)

    print("Loading & building samples ...")
    samples = gather_samples(args.merged_db, args.graded_db, args.emb_dim)
    print(f"Total samples (paper × task groups): {len(samples)}")

    dataset = TruthAggDataset(samples)
    n_total = len(dataset)
    n_train = int(n_total * args.train_ratio)
    n_val = n_total - n_train
    train_set, val_set = random_split(dataset, [n_train, n_val], generator=torch.Generator().manual_seed(args.seed))

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, collate_fn=collate_variable)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, collate_fn=collate_variable)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = WeightNet(in_dim=FEAT_DIM, hidden=args.hidden).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    print("Start training ...")
    best_combo = float("inf")
    for ep in range(1, args.epochs + 1):
        tr_loss = train_one_epoch(model, train_loader, opt, device, args.alpha_num, args.alpha_text)
        rmse, cos_mean, n_num, n_text = evaluate(model, val_loader, device)
        print(f"[Epoch {ep:03d}] train_loss={tr_loss:.6f}  "
              f"valid_RMSE_num={None if rmse is None else round(rmse,4)}  "
              f"valid_cos_text={None if cos_mean is None else round(cos_mean,4)}  "
              f"(n_num={n_num}, n_text={n_text})")

        # 早停指标：数值 RMSE + (1 - 文本余弦)
        combo = (rmse if rmse is not None else 0.0) + (1.0 - (cos_mean if cos_mean is not None else 0.0))
        if combo < best_combo:
            best_combo = combo
            torch.save({"model": model.state_dict(),
                        "cfg": vars(args),
                        "feat_dim": FEAT_DIM},
                       "truth_agg_text_model.pt")
            print("  ✓ saved: truth_agg_text_model.pt")

    print("Done.")


if __name__ == "__main__":
    main()
