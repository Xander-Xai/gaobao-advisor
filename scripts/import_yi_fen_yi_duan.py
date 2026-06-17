#!/usr/bin/env python3
"""
一分一段表数据 — 从已有录取分数线的 min_rank 字段反推
并支持手动导入各省考试院公布的数据（CSV 格式）

策略：
1. 基础数据：从 admission_scores 表的 min_rank 字段反推"分数→位次"映射
2. 准确数据：支持 CSV 导入（T1 数据源）
3. 自动计算等位分：把 2024 年位次查表 → 对应 2023 年分数

数据等级：
- 反推位次：T3（基于录取数据估算，仅作参考）
- CSV 导入：T1（各省考试院官方）
"""

import csv
import os
import sqlite3
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def reverse_engineer_rank_table(db_path: str = None) -> dict:
    """从 admission_scores 表的 min_rank 字段反推分数-位次关系"""
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 按 (省份, 年份, subject_type) 分组，统计 min_score -> min_rank
    cur.execute("""
        SELECT province, year, subject_type, min_score, min_rank
        FROM admission_scores
        WHERE min_score IS NOT NULL AND min_rank IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()

    # 按 (province, year, subject_type) 分组
    groups = defaultdict(list)
    for province, year, subject, score, rank in rows:
        groups[(province, year, subject)].append((score, rank))

    # 对每组，构建 score -> rank 映射
    result = {}
    for key, items in groups.items():
        # 按 score 排序去重
        score_rank = {}
        for score, rank in sorted(items, key=lambda x: -x[0]):
            # 多个学校同分取最优位次
            if score not in score_rank or rank < score_rank[score]:
                score_rank[score] = rank
        result[key] = score_rank

    return result


def query_rank_for_score(province: str, year: int, subject_type: str, score: int, db_path: str = None) -> int | None:
    """查询某分数在 (省份, 年份, 科类) 下的位次（线性插值近似）

    智能匹配 subject_type: 物理/物理类/物 → 3+3综合/物理/理科任一即可
    """
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 智能匹配 subject_type: 物理/物理类/物 → 多种可能
    subject_aliases = {
        "物理": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "物理类": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "物": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "历史": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "历史类": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "史": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "理科": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "文科": ["3+3综合", "历史", "历史类", "综合", "文科"],
    }
    candidates = subject_aliases.get(subject_type, [subject_type])

    # 查询数据库中所有该 (province, year) 下的录取数据，按 subject_type IN (...)
    placeholders = ",".join(["?"] * len(candidates))
    cur.execute(
        f"""
        SELECT min_score, min_rank
        FROM admission_scores
        WHERE province = ? AND year = ? AND subject_type IN ({placeholders})
          AND min_score IS NOT NULL AND min_rank IS NOT NULL
    """,
        (province, year, *candidates),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    # 找到该分数对应的位次（最近邻近似）
    score_to_rank = {}
    for s, r in rows:
        if s not in score_to_rank or r < score_to_rank[s]:
            score_to_rank[s] = r

    if score in score_to_rank:
        return score_to_rank[score]

    # 找最接近的分数（向下取整的位次）
    # 收集所有 <= score 的分数，从中找最大的（最接近且不大于 score）
    sorted_scores = sorted(score_to_rank.items(), key=lambda x: -x[0])  # 降序
    for s, r in sorted_scores:
        if s <= score:
            return r
    # 分数比所有数据都低，返回最低分对应的位次（最差的位次）
    return sorted_scores[-1][1] if sorted_scores else None


def query_score_for_rank(province: str, year: int, subject_type: str, rank: int, db_path: str = None) -> int | None:
    """查询某位次对应的分数（等位分，等位分计算用）"""
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    subject_aliases = {
        "物理": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "物理类": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "物": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "历史": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "历史类": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "史": ["3+3综合", "历史", "历史类", "综合", "文科"],
        "理科": ["3+3综合", "物理", "物理类", "综合", "理科"],
        "文科": ["3+3综合", "历史", "历史类", "综合", "文科"],
    }
    candidates = subject_aliases.get(subject_type, [subject_type])
    placeholders = ",".join(["?"] * len(candidates))

    cur.execute(
        f"""
        SELECT min_score, min_rank
        FROM admission_scores
        WHERE province = ? AND year = ? AND subject_type IN ({placeholders})
          AND min_score IS NOT NULL AND min_rank IS NOT NULL
    """,
        (province, year, *candidates),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    score_to_rank = {}
    for s, r in rows:
        if s not in score_to_rank or r < score_to_rank[s]:
            score_to_rank[s] = r

    # 找最接近的位次
    closest = None
    min_diff = float("inf")
    for s, r in score_to_rank.items():
        diff = abs(r - rank)
        if diff < min_diff:
            min_diff = diff
            closest = s
    return closest


def import_yifenyd_csv(csv_path: str, province: str, year: int, subject_type: str, db_path: str = None) -> int:
    """
    从 CSV 文件导入一分一段表
    CSV 格式: score,count (或 score,count,cumulative_count)
    来源：各省考试院官网发布
    """
    # 此函数预留用于将来直接导入 T1 官方数据
    # 当前未在数据库中建表，所以先打印统计
    imported = 0
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for _row in reader:
            imported += 1
    print(f"  {csv_path}: 解析到 {imported} 行")
    return imported


def populate_from_admission_scores(db_path: str = None) -> int:
    """从 admission_scores 表反推并写入 yi_fen_yi_duan 表。

    策略：
    - 查询 admission_scores 中 min_score > 0 AND min_rank > 0 的记录
    - 按 (province, year, subject_type, min_score) 去重，同分取最小 rank（最优位次）
    - 使用 INSERT OR IGNORE 跳过已存在的记录
    - 返回本次新插入的记录数
    """
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. 从 admission_scores 提取去重后的 (province, year, subject_type, score, rank)
    #    同一分取最优位次（最小 rank）
    cur.execute("""
        SELECT province, year, subject_type, min_score AS score, MIN(min_rank) AS rank
        FROM admission_scores
        WHERE min_score > 0 AND min_rank > 0
        GROUP BY province, year, subject_type, min_score
    """)
    rows = cur.fetchall()
    print(f"  从 admission_scores 提取到 {len(rows)} 个去重 (省份,年份,科类,分数) 组合")

    if not rows:
        conn.close()
        return 0

    # 2. 批量插入 yi_fen_yi_duan，跳过重复
    inserted = 0
    for province, year, subject_type, score, rank in rows:
        cur.execute(
            """
            INSERT OR IGNORE INTO yi_fen_yi_duan (province, year, subject_type, score, cumulative_count)
            VALUES (?, ?, ?, ?, ?)
        """,
            (province, year, subject_type, score, rank),
        )
        if cur.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    print(f"  新插入 {inserted} 条记录到 yi_fen_yi_duan 表")
    return inserted


def check_missing_yfyd(db_path=None):
    """检测一分一段表缺失的省-年份组合"""
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 获取所有有录取数据的 (province, year) 组合
    cur.execute("""
        SELECT DISTINCT province, year FROM admission_scores
        ORDER BY province, year
    """)
    score_combos = set(cur.fetchall())

    # 获取一分一段表已有的 (province, year) 组合
    cur.execute("""
        SELECT DISTINCT province, year FROM yi_fen_yi_duan
    """)
    yfyd_combos = set(cur.fetchall())

    # 找缺失
    missing = score_combos - yfyd_combos

    print(f"  录取数据组合: {len(score_combos)}")
    print(f"  一分一段表组合: {len(yfyd_combos)}")
    print(f"  缺失组合: {len(missing)}")

    for prov, year in sorted(missing):
        cur.execute("""
            SELECT DISTINCT subject_type FROM admission_scores
            WHERE province=? AND year=? AND min_rank IS NOT NULL
        """, (prov, year))
        types = [r[0] for r in cur.fetchall()]
        print(f"    {prov} {year}: 需要 {', '.join(types)}")

    conn.close()
    return missing


def backfill_missing_yfyd(db_path=None):
    """对缺失组合从 admission_scores 反推一分一段表"""
    missing = check_missing_yfyd(db_path)
    if not missing:
        print("  无缺失，跳过")
        return 0

    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    total_inserted = 0
    for prov, year in sorted(missing):
        cur.execute("""
            SELECT subject_type, min_score AS score, MIN(min_rank) AS rank
            FROM admission_scores
            WHERE province=? AND year=? AND min_score > 0 AND min_rank > 0
            GROUP BY subject_type, min_score
        """, (prov, year))
        rows = cur.fetchall()

        inserted = 0
        for subject_type, score, rank in rows:
            cur.execute(
                "INSERT OR IGNORE INTO yi_fen_yi_duan (province, year, subject_type, score, cumulative_count) VALUES (?, ?, ?, ?, ?)",
                (prov, year, subject_type, score, rank),
            )
            if cur.rowcount > 0:
                inserted += 1

        conn.commit()
        total_inserted += inserted
        print(f"    {prov} {year}: 新增 {inserted} 条")

    conn.close()
    print(f"  反推总计新增: {total_inserted} 条")
    return total_inserted


def main():
    print("=" * 60)
    print("  一分一段表数据 - 反推 + 查询工具")
    print("=" * 60)

    # 阶段 -1: 检测并补全缺失
    print("\n>>> 阶段 -1: 检测并补全缺失的一分一段表")
    missing = check_missing_yfyd()
    if missing:
        backfill_missing_yfyd()
    print()

    # 0. 写入 yi_fen_yi_duan 表
    print("\n>>> 阶段 0: 从 admission_scores 反推并写入 yi_fen_yi_duan 表")
    inserted = populate_from_admission_scores()
    print(f"  共写入 {inserted} 条记录")

    # 1. 反推分数-位次映射（内存视图）
    print("\n>>> 阶段 1: 从 admission_scores 表反推位次分布")
    rank_table = reverse_engineer_rank_table()

    if not rank_table:
        print("  [WARN] 数据库中无录取数据，无法反推")
        print("  建议先运行: python scripts/import_baidu_gaokao.py --scores-only")
        return

    # 输出统计
    print(f"\n  反推得到 {len(rank_table)} 个 (省份-年份-科类) 组合的位次分布:")
    for (prov, year, subj), score_rank in sorted(rank_table.items())[:20]:
        max_s = max(score_rank.keys())
        min_s = min(score_rank.keys())
        print(f"    {prov} {year} {subj}: {len(score_rank)} 个分数点 (范围 {min_s}-{max_s})")

    # 2. 查询测试
    print("\n>>> 阶段 2: 查询测试")
    test_cases = [
        ("广东", 2024, "物理类", 700),
        ("广东", 2024, "物理类", 650),
        ("广东", 2024, "物理类", 600),
        ("北京", 2024, "3+3综合", 680),
        ("北京", 2024, "3+3综合", 600),
        ("河南", 2024, "理科", 600),
        ("河南", 2024, "理科", 650),
        ("浙江", 2024, "3+3综合", 700),
    ]
    for prov, yr, subj, score in test_cases:
        rank = query_rank_for_score(prov, yr, subj, score)
        if rank:
            print(f"  {prov} {yr} {score}分 → 位次约 {rank:,}")
        else:
            print(f"  {prov} {yr} {score}分 → [无数据]")

    # 3. 等位分计算测试
    print("\n>>> 阶段 3: 等位分计算测试")
    if ("广东", 2024, "3+3综合") in rank_table and ("广东", 2023, "3+3综合") in rank_table:
        # 假设用户 2024 年位次为 5000，查 2023 年等位分
        target_rank = 5000
        score_2024 = query_score_for_rank("广东", 2024, "3+3综合", target_rank)
        score_2023 = query_score_for_rank("广东", 2023, "3+3综合", target_rank)
        print(f"  广东位次 {target_rank}:")
        print(f"    2024年等位分: {score_2024}")
        print(f"    2023年等位分: {score_2023}")

    print("\n[完成] 一分一段表数据就绪")
    print("  可用接口: query_rank_for_score() / query_score_for_rank()")


if __name__ == "__main__":
    main()
