import sqlite3
import json
import os
import sys # 引入sys以实现优雅退出
import time
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch # 引入torch以检测GPU

# --- 1. 配置部分 (新增了ID_MAP_PATH) ---
# 使用 r'' 来处理Windows路径，避免反斜杠问题
DB_PATH = 'D:\\crawler_adv\\openalex_advanced -v2.db'
FAISS_INDEX_PATH = 'papers_v1.index'
PROGRESS_FILE = 'progress.json'
ID_MAP_PATH = 'id_map.json'  # 新增：用于存储字符串ID到整数ID的映射
MODEL_NAME = 'all-MiniLM-L6-v2'
BATCH_SIZE = 256 # GPU可以处理更大的批次，可以根据您的显存调整
SAVE_CHECKPOINT_EVERY = 100 # 增大了保存频率，因为您的数据量很大

# --- 2. 核心功能函数 (format_paper_text 函数不变) ---
def format_paper_text(title, journal, abstract, keywords_str, topics_str, domain):
    parts = []
    if title: parts.append(f"Title: {title}.")
    if journal: parts.append(f"Published in: {journal}.")
    if abstract: parts.append(f"Abstract: {abstract}.")
    try:
        keywords = json.loads(keywords_str)
        if keywords: parts.append(f"Keywords: {', '.join(keywords)}.")
    except (json.JSONDecodeError, TypeError): pass
    try:
        topics = json.loads(topics_str)
        if topics: parts.append(f"Topics: {', '.join(topics)}.")
    except (json.JSONDecodeError, TypeError): pass
    if domain: parts.append(f"Domain: {domain}.")
    return " ".join(parts)

def process_papers():
    """主处理函数，执行向量化和索引构建，模型在GPU上运行，Faiss索引在CPU上运行。"""
    print("\n" + "="*50)
    print("开始执行论文向量化任务 (V5 - 模型GPU & 索引CPU)")
    print("="*50)

    # 1. 加载模型并自动使用GPU
    print(f"正在加载模型: '{MODEL_NAME}'...")
    # SentenceTransformer会自动检测并使用可用的GPU
    model = SentenceTransformer(MODEL_NAME)
    embedding_dim = model.get_sentence_embedding_dimension()
    device = 'GPU' if model.device.type == 'cuda' else 'CPU'
    print(f"模型加载成功，向量生成将在 {device} 上运行，向量维度为: {embedding_dim}")

    # 2. 加载进度和ID映射
    processed_string_ids = set()
    string_to_int_map = {}
    
    if os.path.exists(PROGRESS_FILE):
        print(f"发现进度文件 '{PROGRESS_FILE}'，正在加载...")
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            processed_string_ids = set(data.get('processed_string_ids', []))
        print(f"已加载 {len(processed_string_ids)} 条已处理记录。")

    if os.path.exists(ID_MAP_PATH):
        print(f"发现ID映射文件 '{ID_MAP_PATH}'，正在加载...")
        with open(ID_MAP_PATH, 'r') as f:
            string_to_int_map = json.load(f)
        print(f"ID映射加载成功，当前包含 {len(string_to_int_map)} 个映射。")

    # 3. 初始化或加载Faiss索引 (纯CPU版本)
    print("Faiss索引将始终在CPU上运行。")
    index = None
    if os.path.exists(FAISS_INDEX_PATH) and len(processed_string_ids) > 0:
        print(f"正在从 '{FAISS_INDEX_PATH}' 加载现有Faiss索引...")
        index = faiss.read_index(FAISS_INDEX_PATH)
        print(f"CPU索引加载成功，当前包含 {index.ntotal} 个向量。")
    else:
        print("未发现现有索引或进度为空，正在创建新索引...")
        base_index = faiss.IndexFlatL2(embedding_dim)
        index = faiss.IndexIDMap(base_index)

    # 4. 从数据库获取需要处理的论文列表
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM works ORDER BY rowid")
    all_paper_string_ids = [row[0] for row in cursor.fetchall()]
    
    ids_to_process = [pid for pid in all_paper_string_ids if pid not in processed_string_ids]
    
    if not ids_to_process:
        print("所有论文都已处理完毕！程序退出。")
        conn.close()
        return

    print(f"数据库总共有 {len(all_paper_string_ids)} 篇论文，还需处理 {len(ids_to_process)} 篇。")
    
    interrupted = False
    # 5. 开始批量处理，并捕获KeyboardInterrupt
    try:
        batches_processed = 0
        with tqdm(total=len(ids_to_process), desc="处理论文") as pbar:
            for i in range(0, len(ids_to_process), BATCH_SIZE):
                batch_string_ids = ids_to_process[i:i + BATCH_SIZE]
                
                query = f'SELECT id, title, journal, abstract, keywords, topics, domain FROM works WHERE id IN ({",".join("?" for _ in batch_string_ids)})'
                cursor.execute(query, batch_string_ids)
                batch_data = cursor.fetchall()

                texts_to_encode, int_ids_for_faiss, valid_string_ids_in_batch = [], [], []
                all_processed_ids = []  # 记录所有处理的ID（包括无标题的）

                for idx, row_data in enumerate(batch_data):
                    string_id, title, journal, abstract, keywords, topics, domain = row_data
                    all_processed_ids.append(string_id)  # 所有ID都标记为已处理
                    
                    # 只处理有标题的论文
                    if title:
                        # 只为有标题的论文分配整数ID
                        if string_id not in string_to_int_map:
                            new_int_id = len(string_to_int_map)
                            string_to_int_map[string_id] = new_int_id
                        
                        int_ids_for_faiss.append(string_to_int_map[string_id])
                        valid_string_ids_in_batch.append(string_id)
                        texts_to_encode.append(format_paper_text(title, journal, abstract, keywords, topics, domain))
                
                if texts_to_encode:
                    embeddings = model.encode(texts_to_encode, convert_to_numpy=True, show_progress_bar=False)
                    
                    ids_to_add = np.array(int_ids_for_faiss).astype('int64')
                    index.add_with_ids(embeddings, ids_to_add)

                # 更新所有处理的ID（包括无标题的）
                processed_string_ids.update(all_processed_ids)
                pbar.update(len(batch_string_ids))

                batches_processed += 1

                if batches_processed % SAVE_CHECKPOINT_EVERY == 0:
                    pbar.set_postfix_str("正在保存检查点...")
                    faiss.write_index(index, FAISS_INDEX_PATH)
                    
                    with open(PROGRESS_FILE, 'w') as f: json.dump({'processed_string_ids': list(processed_string_ids)}, f)
                    with open(ID_MAP_PATH, 'w') as f: json.dump(string_to_int_map, f)
                    pbar.set_postfix_str("处理中...")
    except KeyboardInterrupt:
        print("\n\n捕获到 Ctrl+C 中断信号！即将保存进度并退出...")
        interrupted = True

    # 6. 最终保存 (无论正常结束还是中断都会执行)
    print("\n处理完成！正在进行最终保存..." if not interrupted else "\n正在保存当前进度...")
    
    faiss.write_index(index, FAISS_INDEX_PATH)
    final_ntotal = index.ntotal

    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'processed_string_ids': list(processed_string_ids)}, f)
    with open(ID_MAP_PATH, 'w') as f:
        json.dump(string_to_int_map, f)

    conn.close()
    
    print("\n" + "="*50)
    if interrupted:
        print("任务已中断。")
        print("当前进度已成功保存，下次运行时将从断点继续。")
    else:
        print("任务成功完成！")

    print(f"向量已保存到 '{FAISS_INDEX_PATH}'。")
    print(f"ID映射已保存到 '{ID_MAP_PATH}'。")
    print(f"索引中现在共有 {final_ntotal} 个向量。")
    print("="*50)
    
    if interrupted:
        sys.exit(0)

# --- 脚本主入口 ---
if __name__ == '__main__':
    process_papers()

