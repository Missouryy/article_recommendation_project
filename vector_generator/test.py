import faiss
import json
import sqlite3
import numpy as np
import random
import sys
import os

# --- 1. 配置部分 (请确保这些文件与脚本在同一目录，或使用绝对路径) ---
DB_PATH = r'D:\crawler_adv\openalex_advanced.db'
FAISS_INDEX_PATH = 'papers_v3.index'
ID_MAP_PATH = 'id_map_v3.json'
RECOMMENDATION_COUNT = 100  # 您希望推荐的论文数量

# --- 2. 辅助函数与核心推荐逻辑 ---

def load_resources():
    """加载Faiss索引和ID映射表。"""
    print("="*50)
    print("开始加载推荐所需资源...")

    if not all(os.path.exists(p) for p in [FAISS_INDEX_PATH, ID_MAP_PATH, DB_PATH]):
        print("\n[错误] 缺少必要文件！请确保以下文件存在于正确路径：")
        print(f" - Faiss索引: {FAISS_INDEX_PATH}")
        print(f" - ID映射: {ID_MAP_PATH}")
        print(f" - 数据库: {DB_PATH}")
        sys.exit(1)

    print(f"正在从 '{FAISS_INDEX_PATH}' 加载Faiss索引...")
    index = faiss.read_index(FAISS_INDEX_PATH)
    print(f"索引加载成功，包含 {index.ntotal} 个向量。")

    print(f"正在从 '{ID_MAP_PATH}' 加载ID映射...")
    with open(ID_MAP_PATH, 'r', encoding='utf-8') as f:
        string_to_int_map = json.load(f)
    # 创建一个反向映射，用于从整数ID找回字符串ID
    int_to_string_map = {v: k for k, v in string_to_int_map.items()}
    print(f"ID映射加载成功，包含 {len(string_to_int_map)} 个条目。")
    
    print("所有资源加载完毕！")
    print("="*50)
    return index, string_to_int_map, int_to_string_map

def get_titles_from_db(string_ids):
    """根据字符串ID列表，从数据库查询论文标题。"""
    # 如果ID列表为空，直接返回空字典，避免空的IN子句导致SQL错误
    if not string_ids:
        return {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f'SELECT id, title FROM works WHERE id IN ({",".join("?" for _ in string_ids)})'
    cursor.execute(query, string_ids)
    # 创建一个字典以便快速查找
    title_map = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return title_map

def recommend_for_user(index, string_to_int_map, int_to_string_map, read_history, favorite_history, top_k=100):
    """为用户生成推荐。"""
    print("\n开始为用户生成推荐...")
    
    # --- 步骤1: 将历史记录的字符串ID转换为整数ID ---
    history_int_ids = []
    weights = []
    
    # 为收藏历史赋予更高权重
    for string_id in favorite_history:
        if string_id in string_to_int_map:
            history_int_ids.append(string_to_int_map[string_id])
            weights.append(1.5) # 收藏的权重为1.5
    
    # 为阅读历史赋予普通权重
    for string_id in read_history:
        if string_id in string_to_int_map:
            history_int_ids.append(string_to_int_map[string_id])
            weights.append(1.0) # 阅读的权重为1.0

    if not history_int_ids:
        print("用户历史为空，无法生成个性化推荐。")
        return []

    print(f"根据 {len(history_int_ids)} 条有效历史记录生成用户画像...")

    # --- 步骤2: 获取历史向量并计算加权平均值 ---
    ids_to_reconstruct = np.array(history_int_ids, dtype='int64')
    
    # 修正：IndexIDMap本身不支持reconstruct，需要调用其内部的基础索引(index.index)。
    base_index = index.index
    history_vectors_list = [base_index.reconstruct(int(i)) for i in ids_to_reconstruct]
    history_vectors = np.array(history_vectors_list)
    
    # 计算加权平均向量
    weights = np.array(weights).reshape(-1, 1)
    user_profile_vector = np.sum(history_vectors * weights, axis=0) / np.sum(weights)
    
    # 修正：Faiss的底层C++代码期望接收float32类型的numpy数组
    user_profile_vector_float32 = user_profile_vector.astype(np.float32)
    # 将用户画像向量归一化，这对于相似度计算很重要
    faiss.normalize_L2(user_profile_vector_float32.reshape(1, -1))
    
    print("用户画像向量生成成功。")

    # --- 步骤3: 使用用户画像向量在Faiss中进行搜索 ---
    # 我们需要多搜索一些结果，因为需要过滤掉用户已知的论文
    num_to_search = top_k + len(read_history) + len(favorite_history)
    print(f"正在Faiss索引中搜索 {num_to_search} 个最相似的向量...")
    
    # D是距离（相似度），I是整数ID
    # 使用转换后的float32向量进行搜索
    distances, neighbor_int_ids = index.search(user_profile_vector_float32.reshape(1, -1), num_to_search)
    
    # --- 步骤4: 过滤掉已知论文并格式化结果 ---
    user_known_ids = set(read_history + favorite_history)
    recommendations = []
    
    print("正在过滤已读和已收藏的论文...")
    for int_id in neighbor_int_ids[0]:
        # Faiss可能会返回-1作为无效ID
        if int_id == -1:
            continue
            
        # 修正：使用整数键进行查找
        string_id = int_to_string_map.get(int_id)
        if string_id and string_id not in user_known_ids:
            recommendations.append(string_id)
        
        if len(recommendations) >= top_k:
            break
            
    return recommendations

# --- 脚本主入口 ---
if __name__ == '__main__':
    # 加载核心资源
    faiss_index, s_to_i_map, i_to_s_map = load_resources()

    # --- 模拟一个用户的历史记录 ---
    # 从ID映射中取前几个ID来模拟，确保领域集中
    all_known_ids = list(s_to_i_map.keys())
    if len(all_known_ids) < 20:
        print("[警告] ID映射中的ID数量不足20个，将使用所有可用ID进行模拟。")
        simulation_ids = all_known_ids
    else:
        # 修正：取列表的倒数20个ID
        simulation_ids = all_known_ids[1500000:1500020]

    user_read_history = simulation_ids[:10]
    user_favorite_history = simulation_ids[10:]
    
    # 打印用户的模拟历史，并获取标题让其更可读
    history_titles = get_titles_from_db(user_read_history + user_favorite_history)
    print("\n--- 模拟用户历史 ---")
    print("【收藏历史 (权重1.5)】:")
    for i, string_id in enumerate(user_favorite_history):
        print(f"  {i+1}. {history_titles.get(string_id, '未知标题')} ({string_id})")

    print("\n【阅读历史 (权重1.0)】:")
    for i, string_id in enumerate(user_read_history):
        print(f"  {i+1}. {history_titles.get(string_id, '未知标题')} ({string_id})")
    print("--------------------")

    # 为该用户生成推荐
    recommended_ids = recommend_for_user(
        faiss_index,
        s_to_i_map,
        i_to_s_map,
        user_read_history,
        user_favorite_history,
        top_k=RECOMMENDATION_COUNT
    )

    # 打印推荐结果
    if recommended_ids:
        print(f"\n✅ 成功为用户生成 {len(recommended_ids)} 条推荐！")
        print("\n--- Top 100 推荐论文列表 ---")
        
        # 获取推荐结果的标题
        recommended_titles = get_titles_from_db(recommended_ids)
        
        for i, string_id in enumerate(recommended_ids):
            title = recommended_titles.get(string_id, '未知标题')
            print(f"  {i+1:3d}. {title} ({string_id})")
    else:
        print("\n❌ 未能生成任何推荐。")

