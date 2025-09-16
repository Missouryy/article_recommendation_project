import sqlite3
import requests
import time
import random
import ssl
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

# ------------------- 配置参数（关键修改） -------------------
TARGET_AUTHOR_COUNT = 1000  # 目标爬取数量
OUTPUT_DB_PATH = "author_db.db"
OPENALEX_AUTHOR_API = "https://api.openalex.org/authors"
OPENALEX_WORKS_API = "https://api.openalex.org/works"
CONCURRENCY = 5  # 并发抓取线程数（谨慎调大，避免触发限流）
# 可选：为 OpenAlex 添加 mailto 便于联系（建议填写真实邮箱）
MAILTO = ""

# 更真实的请求头（降低被识别为爬虫的概率）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}

# 简化筛选条件：只保留“论文数量>10篇”（确保有结果），去掉可能无效的学科筛选
# 这样能获取任意领域有一定产出的作者
SUBJECT_FILTER = "works_count:>10"

# ------------------- 解决SSL证书问题（可选） -------------------
# 部分环境可能因证书问题导致连接失败，添加此配置（谨慎使用，仅测试用）
ssl._create_default_https_context = ssl._create_unverified_context

# 复用 HTTP 连接以提升效率
session = requests.Session()
session.trust_env = False  # 忽略系统环境代理，避免被本地代理重定向到 127.0.0.1


def _with_mailto(params: dict) -> dict:
    """如果配置了 MAILTO，则在请求参数中加入 mailto。"""
    if MAILTO:
        params = dict(params)
        params["mailto"] = MAILTO
    return params

# ------------------- 工具函数：机构解析与回退 -------------------
def get_institution_from_author_data(author_json):
    """从作者详情中提取机构名，兼容新版与旧版字段。

    优先顺序：last_known_institutions[0].display_name → last_known_institution.display_name → affiliations 中的 institution.display_name → None

    返回: (institution_name, source)
    source ∈ {"last_known_institutions", "last_known_institution", "affiliations", "none"}
    """
    try:
        # 新版：数组字段
        last_insts = author_json.get("last_known_institutions")
        if isinstance(last_insts, list) and last_insts:
            first = (last_insts[0] or {})
            name = first.get("display_name")
            if name:
                return name, "last_known_institutions"

        # 旧版：单个对象或字符串
        last_inst = author_json.get("last_known_institution")
        if isinstance(last_inst, dict):
            name = last_inst.get("display_name")
            if name:
                return name, "last_known_institution"
        if isinstance(last_inst, str) and last_inst:
            return last_inst, "last_known_institution"

        # 兜底：affiliations 数组
        affs = author_json.get("affiliations")
        if isinstance(affs, list) and affs:
            # 选择 years 中最大年份对应的机构
            best = None
            best_year = -1
            for aff in affs:
                if not isinstance(aff, dict):
                    continue
                years = aff.get("years") or []
                if isinstance(years, list) and years:
                    last_year = max(y for y in years if isinstance(y, int)) if any(isinstance(y, int) for y in years) else -1
                else:
                    last_year = -1
                inst = (aff.get("institution") or {}) if isinstance(aff.get("institution"), dict) else {}
                name = inst.get("display_name")
                if name and last_year >= 0 and last_year > best_year:
                    best = name
                    best_year = last_year
            if best:
                return best, "affiliations"
    except Exception:
        pass
    return None, "none"


def infer_institution_from_works(author_id, max_pages: int = 12):
    """当作者 last_known_institution 为空时，从其论文作者信息中推断机构。

    策略：分页查若干篇论文，统计作者位下的 institutions.display_name；
    若结构化机构缺失，则用 raw_affiliation_string 做启发式解析；
    返回出现频率最高的机构名。
    """
    full_author_id_url = f"https://openalex.org/{author_id}"
    institution_counter = Counter()

    try:
        for page in range(1, max_pages + 1):
            params = {
                "filter": f"authorships.author.id:{full_author_id_url}",
                "per_page": 50,
                "page": page,
                "sort": "publication_date:desc",
            }
            response = session.get(
                OPENALEX_WORKS_API,
                params=_with_mailto({
                    **params,
                    "select": "authorships.author.id,authorships.institutions.display_name,authorships.raw_affiliation_string"
                }),
                headers=HEADERS,
                timeout=(10, 30),
                verify=False
            )
            if response.status_code != 200:
                break

            data = response.json()
            results = data.get("results", [])
            if not results:
                break

            for work in results:
                authorships = work.get("authorships", []) if isinstance(work.get("authorships"), list) else []
                for authorship in authorships:
                    author_field = authorship.get("author", {}) or {}
                    author_id_in_work = author_field.get("id")
                    if not author_id_in_work:
                        continue
                    if author_id_in_work != full_author_id_url and not author_id_in_work.endswith(f"/{author_id}"):
                        continue

                    institutions = authorship.get("institutions", [])
                    added = False
                    for inst in institutions if isinstance(institutions, list) else []:
                        name = (inst or {}).get("display_name")
                        if name:
                            institution_counter[name] += 1
                            added = True

                    if not added:
                        raw_aff = (authorship or {}).get("raw_affiliation_string") or ""
                        if raw_aff:
                            # 先按分号/竖线拆，再按逗号拆，取靠后的较长片段
                            primary = raw_aff
                            for sep in [";", "|"]:
                                if sep in primary:
                                    primary = primary.split(sep)[0]
                            comma_parts = [p.strip() for p in primary.split(",") if p and len(p.strip()) > 2]
                            if comma_parts:
                                institution_counter[comma_parts[-1]] += 1

        if not institution_counter:
            return None
        return institution_counter.most_common(1)[0][0]
    except Exception:
        return None

def run_full_crawl():
    # ------------------- 步骤1：批量获取作者ID -------------------
    author_ids = []
    current_page = 1
    max_retries = 5  # 提高重试次数
    print("开始获取作者ID...")

    while len(author_ids) < TARGET_AUTHOR_COUNT * 2:
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            params = {
                "filter": SUBJECT_FILTER,
                "per_page": 200,
                "page": current_page,
                "sort": "works_count:desc",  # 按论文数量排序，优先获取活跃作者
                "select": "id"
            }

            try:
                # 增加超时时间，设置连接和读取超时
                response = session.get(
                    OPENALEX_AUTHOR_API,
                    params=_with_mailto(params),
                    headers=HEADERS,
                    timeout=(10, 30),  # 连接超时10秒，读取超时30秒
                    verify=False  # 关闭SSL验证（解决部分环境证书问题）
                )

                if response.status_code == 200:
                    data = response.json()
                    total_results = data.get("meta", {}).get("total_results", 0)
                    results = data.get("results", [])

                    print(f"第{current_page}页 - 总结果数: {total_results}, 本页结果数: {len(results)}")

                    if not results:
                        print("⚠️ 本页无结果，已到达数据末尾")
                        success = True
                        break

                    # 提取作者ID
                    new_ids = [r["id"].replace("https://openalex.org/", "") for r in results]
                    author_ids.extend(new_ids)
                    print(f"✅ 累计获取作者ID: {len(author_ids)}")

                    current_page += 1
                    success = True

                else:
                    print(f"❌ 第{current_page}页请求失败，状态码: {response.status_code}")
                    retry_count += 1
                    time.sleep(10)  # 失败后延长等待时间

            except Exception as e:
                print(f"❌ 第{current_page}页请求出错: {str(e)}")
                retry_count += 1
                time.sleep(10)  # 网络错误后等待更长时间

        if not success:
            print(f"❌ 第{current_page}页多次重试失败，终止获取")
            break

        # 进一步延长请求间隔，避免触发限流
        time.sleep(random.uniform(5, 8))

    # 去重
    author_ids = list(set(author_ids))
    print(f"\n📊 去重后共获取到 {len(author_ids)} 个作者ID")

    # ------------------- 步骤2：创建数据库表 -------------------
    conn = sqlite3.connect(OUTPUT_DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS authors
                   (
                       openalex_id
                       TEXT
                       PRIMARY
                       KEY,
                       display_name
                       TEXT
                       NOT
                       NULL,
                       orcid
                       TEXT,
                       institution
                       TEXT,
                       research_areas
                       TEXT,
                       cited_by_count
                       INTEGER
                       DEFAULT
                       0,
                       works_count
                       INTEGER
                       DEFAULT
                       0,
                       first_publication_year
                       INTEGER,
                       last_publication_year
                       INTEGER
                   )
                   ''')
    conn.commit()

    # ------------------- 步骤3：获取作者详情并保存 -------------------
    success_count = 0
    fail_count = 0

    print("\n开始获取作者详情...")
    for idx, author_id in enumerate(author_ids):
        if success_count >= TARGET_AUTHOR_COUNT:
            break

        print(f"\n处理第{idx + 1}/{len(author_ids)}个作者 (ID: {author_id})")
        detail_url = f"{OPENALEX_AUTHOR_API}/{author_id}"
        retry_count = 0
        saved = False

        while retry_count < max_retries and not saved:
            try:
                response = session.get(
                    detail_url,
                    params=_with_mailto({
                        "select": "display_name,orcid,last_known_institutions,last_known_institution,affiliations,x_concepts,cited_by_count,works_count,first_publication_year,last_publication_year"
                    }),
                    headers=HEADERS,
                    timeout=(10, 30),
                    verify=False
                )

                if response.status_code == 200:
                    data = response.json()
                    # 机构解析与回退
                    institution_name, institution_source = get_institution_from_author_data(data)
                    if not institution_name:
                        inferred_name = infer_institution_from_works(author_id)
                        if inferred_name:
                            institution_name = inferred_name
                            institution_source = "works_authorships"
                        else:
                            institution_name = "未知机构"
                            institution_source = "unknown"

                    author_info = {
                        "openalex_id": author_id,
                        "display_name": data.get("display_name", "未知作者"),
                        "orcid": data.get("orcid", ""),
                        "institution": institution_name,
                        "research_areas": ", ".join(
                            [area["display_name"] for area in data.get("x_concepts", []) if area.get("score", 0) > 0.3]
                        ),
                        "cited_by_count": data.get("cited_by_count", 0),
                        "works_count": data.get("works_count", 0),
                        "first_publication_year": data.get("first_publication_year"),
                        "last_publication_year": data.get("last_publication_year")
                    }

                    cursor.execute('''
                                   INSERT INTO authors (openalex_id, display_name, orcid, institution, research_areas,
                                                        cited_by_count, works_count, first_publication_year,
                                                        last_publication_year)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                   ''', (
                                       author_info["openalex_id"],
                                       author_info["display_name"],
                                       author_info["orcid"],
                                       author_info["institution"],
                                       author_info["research_areas"],
                                       author_info["cited_by_count"],
                                       author_info["works_count"],
                                       author_info["first_publication_year"],
                                       author_info["last_publication_year"]
                                   ))
                    conn.commit()

                    success_count += 1
                    saved = True
                    print(f"✅ 成功保存 (累计: {success_count}/{TARGET_AUTHOR_COUNT}) | 机构: {institution_name} (来源: {institution_source})")

                else:
                    print(f"❌ 详情请求失败，状态码: {response.status_code}")
                    retry_count += 1
                    time.sleep(8)

            except Exception as e:
                print(f"❌ 详情获取出错: {str(e)}")
                retry_count += 1
                time.sleep(8)

        if not saved:
            fail_count += 1
            print(f"❌ 多次重试失败，跳过该作者")

        time.sleep(random.uniform(3, 6))

    # ------------------- 完成处理 -------------------
    print("\n" + "=" * 50)
    print(f"🎉 任务完成")
    print(f"✅ 成功保存: {success_count} 个作者")
    print(f"❌ 失败/跳过: {fail_count} 个作者")
    print(f"📦 数据库文件: {OUTPUT_DB_PATH}")
    conn.close()


def ensure_institution_column(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(authors)")
    cols = [row[1] for row in cursor.fetchall()]
    if "institution" not in cols:
        print("⚙️ 检测到缺少列 institution，正在添加...")
        cursor.execute("ALTER TABLE authors ADD COLUMN institution TEXT")
        conn.commit()


def _fetch_institution_for_author_id(author_id: str) -> tuple[str, str]:
    detail_url = f"{OPENALEX_AUTHOR_API}/{author_id}"
    try:
        # 第一次尝试：带 select 精简返回体
        params = _with_mailto({
            "select": "last_known_institutions,last_known_institution,affiliations,display_name"
        })
        resp = session.get(detail_url, params=params, headers=HEADERS, timeout=(10, 30), verify=False)
        if resp.status_code != 200:
            # 退避：不带 select 再试一次
            resp = session.get(detail_url, params=_with_mailto({}), headers=HEADERS, timeout=(10, 30), verify=False)
            if resp.status_code != 200:
                return "未知机构", "error"
        data = resp.json()
        name, source = get_institution_from_author_data(data)
        if name:
            return name, source
        inferred = infer_institution_from_works(author_id)
        if inferred:
            return inferred, "works_authorships"
        return "未知机构", "unknown"
    except Exception:
        return "未知机构", "exception"


def backfill_institutions(db_path: str, max_workers: int = CONCURRENCY, batch_size: int = 100):
    conn = sqlite3.connect(db_path)
    ensure_institution_column(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT openalex_id FROM authors WHERE institution IS NULL OR institution = '' OR institution = '未知机构'")
    ids = [row[0] for row in cursor.fetchall()]
    total = len(ids)
    if total == 0:
        print("✅ 无需回填，所有作者已具备 institution")
        conn.close()
        return
    print(f"开始回填 institution，共 {total} 条...")

    updated = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_institution_for_author_id, author_id): author_id for author_id in ids}
        batch_updates = []
        for future in as_completed(futures):
            author_id = futures[future]
            try:
                inst, source = future.result()
            except Exception:
                inst, source = "未知机构", "exception"
            batch_updates.append((inst, author_id))
            updated += 1
            if len(batch_updates) >= batch_size:
                cursor.executemany("UPDATE authors SET institution = ? WHERE openalex_id = ?", batch_updates)
                conn.commit()
                print(f"🚀 已回填 {updated}/{total}")
                batch_updates.clear()
        if batch_updates:
            cursor.executemany("UPDATE authors SET institution = ? WHERE openalex_id = ?", batch_updates)
            conn.commit()

    print(f"✅ 回填完成，共更新 {updated} 条记录")
    conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="OpenAlex 作者爬虫与机构回填工具")
    parser.add_argument("--mode", choices=["crawl", "backfill"], default="crawl", help="运行模式：crawl 或 backfill")
    parser.add_argument("--db", default=OUTPUT_DB_PATH, help="数据库路径")
    parser.add_argument("--workers", type=int, default=CONCURRENCY, help="回填时的并发线程数")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "backfill":
        backfill_institutions(args.db, max_workers=args.workers)
    else:
        run_full_crawl()
