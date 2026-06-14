#!/usr/bin/env python3
"""
数据更新管道 — 从百度高考 API 批量拉取录取数据 + 一分一段表

功能:
  1. 拉取指定省份+年份的录取分数线数据，写入 admission_scores 表
  2. 拉取一分一段表数据，写入 yi_fen_yi_duan 表
  3. 幂等：跳过已存在的记录（基于 UniqueConstraint 去重）
  4. 输出统计摘要（新增/跳过/错误）

用法:
  # 拉取湖北 2025 年录取数据
  python scripts/update_data.py --province 湖北 --year 2025

  # 拉取湖北 2025 年一分一段表
  python scripts/update_data.py --province 湖北 --year 2025 --yi-fen-yi-duan

  # 同时拉取录取数据 + 一分一段表
  python scripts/update_data.py --province 湖北 --year 2025 --with-yfdd

  # 全量更新（31 省份 × 近 3 年）
  python scripts/update_data.py --all

  # 全量更新含一分一段表
  python scripts/update_data.py --all --with-yfdd

  # 仅更新一分一段表（全量）
  python scripts/update_data.py --all --yi-fen-yi-duan
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db
from db.models import AdmissionScore, School, YiFenYiDuan
from scrapers.baidu_gaokao import DELAY, _fetch_json, fetch_school_score
from utils import safe_int

# ── 31 个省份 ──
ALL_PROVINCES = [
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
]

# 省份 → 百度 API curriculum 参数映射
PROVINCE_CURRICULUMS = {
    # 3+3 综合（新高考六选三）
    "北京": ["3+3综合"],
    "天津": ["3+3综合"],
    "上海": ["3+3综合"],
    "山东": ["3+3综合"],
    "海南": ["3+3综合"],
    "浙江": ["3+3综合"],
    # 3+1+2（新高考物理/历史）
    "广东": ["物理类", "历史类"],
    "江苏": ["物理类", "历史类"],
    "河北": ["物理类", "历史类"],
    "辽宁": ["物理类", "历史类"],
    "重庆": ["物理类", "历史类"],
    "安徽": ["物理类", "历史类"],
    "福建": ["物理类", "历史类"],
    "湖北": ["物理类", "历史类"],
    "湖南": ["物理类", "历史类"],
    "广西": ["物理类", "历史类"],
    "江西": ["物理类", "历史类"],
    "贵州": ["物理类", "历史类"],
    "甘肃": ["物理类", "历史类"],
    "黑龙江": ["物理类", "历史类"],
    "吉林": ["物理类", "历史类"],
    # 传统文理分科
    "四川": ["理科", "文科"],
    "河南": ["理科", "文科"],
    "山西": ["理科", "文科"],
    "陕西": ["理科", "文科"],
    "云南": ["理科", "文科"],
    "内蒙古": ["理科", "文科"],
    "宁夏": ["理科", "文科"],
    "青海": ["理科", "文科"],
    "新疆": ["理科", "文科"],
}


# ══════════════════════════════════════════════════════════
# 录取数据更新（基于学校维度）
# ══════════════════════════════════════════════════════════


def update_admission_scores(db, province: str, year: int) -> dict:
    """
    为指定省份+年份，遍历数据库中已有的学校，拉取录取数据并写入 admission_scores。
    幂等：基于 (school_id, major_id, province, year, batch, subject_type) 去重。

    Returns:
        dict: {"new": int, "skipped": int, "errors": int, "requests": int}
    """
    stats = {"new": 0, "skipped": 0, "errors": 0, "requests": 0}
    curriculums = PROVINCE_CURRICULUMS.get(province, ["物理类", "历史类"])

    # 获取数据库中已有学校（至少需要有学校才能关联 school_id）
    schools = db.query(School).all()
    if not schools:
        print("  [WARN] 数据库中无学校数据，请先运行 import_baidu_gaokao.py --schools-only")
        return stats

    print(f"\n[录取数据] {province} {year}年 | {len(schools)} 所学校 × {len(curriculums)} 科类")

    for school in schools:
        for curriculum in curriculums:
            try:
                scores = fetch_school_score(school.name, province, year, curriculum)
                stats["requests"] += 1

                if not scores:
                    time.sleep(DELAY / 2)
                    continue

                for s in scores:
                    min_score = safe_int(s.get("minScore"))
                    if min_score is None:
                        stats["skipped"] += 1
                        continue

                    # 幂等检查：按 UniqueConstraint 去重
                    existing = (
                        db.query(AdmissionScore)
                        .filter(
                            AdmissionScore.school_id == school.id,
                            AdmissionScore.major_id.is_(None),
                            AdmissionScore.province == province,
                            AdmissionScore.year == year,
                            AdmissionScore.batch == s.get("batchName", "本科批"),
                            AdmissionScore.subject_type == curriculum,
                        )
                        .first()
                    )

                    if existing:
                        stats["skipped"] += 1
                        continue

                    rec = AdmissionScore(
                        school_id=school.id,
                        major_id=None,
                        province=province,
                        year=year,
                        batch=s.get("batchName", "本科批"),
                        subject_type=curriculum,
                        min_score=min_score,
                        min_rank=safe_int(s.get("minScoreOrder")),
                        plan_count=safe_int(s.get("enrollNum")),
                    )
                    db.add(rec)
                    stats["new"] += 1

                # 每 100 条 commit 一次
                if stats["new"] % 100 == 0 and stats["new"] > 0:
                    db.commit()

                time.sleep(DELAY)

            except Exception as e:
                stats["errors"] += 1
                print(f"  [ERROR] {school.name} {province} {year} {curriculum}: {e}")
                continue

    db.commit()
    return stats


# ══════════════════════════════════════════════════════════
# 一分一段表更新
# ══════════════════════════════════════════════════════════


def fetch_yi_fen_yi_duan(province: str, year: int) -> list[dict]:
    """
    从百度高考 API 拉取一分一段表数据。

    API URL: https://gaokao.baidu.com/api/gkscore?province={province}&year={year}&type=yfyd

    Returns:
        list[dict]: [{"score": int, "count": int, "cumulative_count": int}, ...]
    """
    # 百度 API 省份名需要 URL 编码
    params = urllib.parse.urlencode(
        {
            "province": province,
            "year": str(year),
            "type": "yfyd",
        }
    )
    url = f"https://gaokao.baidu.com/api/gkscore?{params}"
    data = _fetch_json(url)

    if not data:
        return []

    # 解析百度返回的 JSON 结构（兼容多种可能的格式）
    items = []
    raw_data = data.get("data", data)

    # 可能的字段名映射
    if isinstance(raw_data, list):
        row_list = raw_data
    elif isinstance(raw_data, dict):
        # 尝试常见的 key
        row_list = (
            raw_data.get("list", [])
            or raw_data.get("dataList", [])
            or raw_data.get("rows", [])
            or raw_data.get("items", [])
        )
        # 如果 data 本身就是 {score: cumulativeCount, ...} 格式
        if not row_list and not isinstance(raw_data.get("data"), list):
            # 可能 data 是单层 dict: {"680": 100, "679": 200, ...}
            if all(isinstance(k, str) for k in raw_data.keys()):
                for k, v in raw_data.items():
                    try:
                        score = int(k)
                        items.append(
                            {
                                "score": score,
                                "cumulative_count": safe_int(v),
                            }
                        )
                    except ValueError:
                        continue
                return items
    else:
        return []

    for row in row_list:
        if not isinstance(row, dict):
            continue
        score = safe_int(row.get("score") or row.get("mark") or row.get("totalScore"))
        cumulative = safe_int(
            row.get("cumulative_count")
            or row.get("sameCount")
            or row.get("cumulativeNum")
            or row.get("same_num")
            or row.get("totalNum")
        )
        if score is not None and cumulative is not None:
            items.append(
                {
                    "score": score,
                    "cumulative_count": cumulative,
                }
            )

    return items


def update_yi_fen_yi_duan(db, province: str, year: int) -> dict:
    """
    拉取并写入一分一段表数据到 yi_fen_yi_duan 表。
    幂等：基于 (province, year, subject_type, score) 去重。

    一分一段表通常不分科类（新高考省份按物理类/历史类分开设），但百度 API
    返回的数据默认不带科类标识，这里统一标记为 "综合"（可在后续扩展中细分）。

    Returns:
        dict: {"new": int, "skipped": int, "errors": int}
    """
    stats = {"new": 0, "skipped": 0, "errors": 0}
    print(f"\n[一分一段] 拉取 {province} {year}年 ...", end=" ")

    try:
        items = fetch_yi_fen_yi_duan(province, year)
    except Exception as e:
        stats["errors"] += 1
        print(f"拉取失败: {e}")
        return stats

    if not items:
        print("无数据")
        return stats

    print(f"获取到 {len(items)} 条记录")

    for item in items:
        # 幂等检查
        existing = (
            db.query(YiFenYiDuan)
            .filter(
                YiFenYiDuan.province == province,
                YiFenYiDuan.year == year,
                YiFenYiDuan.subject_type == "综合",
                YiFenYiDuan.score == item["score"],
            )
            .first()
        )

        if existing:
            stats["skipped"] += 1
            continue

        rec = YiFenYiDuan(
            province=province,
            year=year,
            subject_type="综合",
            score=item["score"],
            cumulative_count=item["cumulative_count"],
        )
        db.add(rec)
        stats["new"] += 1

    db.commit()
    return stats


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="数据更新管道 — 从百度高考 API 拉取录取数据和一分一段表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/update_data.py --province 湖北 --year 2025\n"
            "  python scripts/update_data.py --province 湖北 --year 2025 --with-yfdd\n"
            "  python scripts/update_data.py --province 湖北 --year 2025 --yi-fen-yi-duan\n"
            "  python scripts/update_data.py --all\n"
            "  python scripts/update_data.py --all --with-yfdd\n"
            "  python scripts/update_data.py --all --yi-fen-yi-duan\n"
        ),
    )
    parser.add_argument("--province", type=str, help="指定省份，如 湖北")
    parser.add_argument("--year", type=int, help="指定年份，如 2025")
    parser.add_argument("--all", action="store_true", help="全量更新（31 个省份）")
    parser.add_argument("--yi-fen-yi-duan", action="store_true", help="仅拉取一分一段表（跳过录取数据）")
    parser.add_argument("--with-yfdd", action="store_true", help="拉取录取数据的同时也拉取一分一段表")
    args = parser.parse_args()

    # 参数校验
    if not args.all and not args.province:
        parser.error("请指定 --province 或 --all")

    # 确定目标省份和年份
    if args.all:
        provinces = ALL_PROVINCES
    else:
        provinces = [args.province]

    current_year = 2026  # 今年
    if args.year:
        years = [args.year]
    elif args.all:
        # 全量模式：近 3 年
        years = [current_year, current_year - 1, current_year - 2]
    else:
        years = [current_year - 1]  # 默认去年

    only_yfdd = args.yi_fen_yi_duan
    with_yfdd = args.with_yfdd

    # 初始化数据库
    init_db()
    db = get_session()

    print("=" * 60)
    print("  数据更新管道")
    print("=" * 60)
    print(f"  省份: {', '.join(provinces) if len(provinces) <= 5 else f'{len(provinces)} 个省份'}")
    print(f"  年份: {years}")
    print(f"  模式: {'仅一分一段表' if only_yfdd else '录取数据' + ('+一分一段表' if with_yfdd else '')}")
    print("=" * 60)

    total_stats = {
        "adm_new": 0,
        "adm_skipped": 0,
        "adm_errors": 0,
        "adm_requests": 0,
        "yfdd_new": 0,
        "yfdd_skipped": 0,
        "yfdd_errors": 0,
    }
    start = time.time()

    try:
        for province in provinces:
            for year in years:
                print(f"\n{'─' * 40}")
                print(f"  {province} {year}年")
                print(f"{'─' * 40}")

                # 录取数据
                if not only_yfdd:
                    adm_stats = update_admission_scores(db, province, year)
                    total_stats["adm_new"] += adm_stats["new"]
                    total_stats["adm_skipped"] += adm_stats["skipped"]
                    total_stats["adm_errors"] += adm_stats["errors"]
                    total_stats["adm_requests"] += adm_stats["requests"]
                    print(
                        f"  录取数据: +{adm_stats['new']} 新增 / "
                        f"{adm_stats['skipped']} 跳过 / {adm_stats['errors']} 错误 "
                        f"/ {adm_stats['requests']} 请求"
                    )

                # 一分一段表
                if only_yfdd or with_yfdd:
                    yfdd_stats = update_yi_fen_yi_duan(db, province, year)
                    total_stats["yfdd_new"] += yfdd_stats["new"]
                    total_stats["yfdd_skipped"] += yfdd_stats["skipped"]
                    total_stats["yfdd_errors"] += yfdd_stats["errors"]
                    print(
                        f"  一分一段: +{yfdd_stats['new']} 新增 / "
                        f"{yfdd_stats['skipped']} 跳过 / {yfdd_stats['errors']} 错误"
                    )

    except KeyboardInterrupt:
        print("\n[中断] 用户取消，正在保存已采集数据...")
        db.commit()
    finally:
        db.close()

    elapsed = time.time() - start

    # 打印统计摘要
    print("\n" + "=" * 60)
    print("  更新完成 — 统计摘要")
    print("=" * 60)

    if not only_yfdd:
        print("  录取数据:")
        print(f"    新增:  {total_stats['adm_new']}")
        print(f"    跳过:  {total_stats['adm_skipped']}（已存在）")
        print(f"    错误:  {total_stats['adm_errors']}")
        print(f"    请求:  {total_stats['adm_requests']}")

    if only_yfdd or with_yfdd:
        print("  一分一段表:")
        print(f"    新增:  {total_stats['yfdd_new']}")
        print(f"    跳过:  {total_stats['yfdd_skipped']}（已存在）")
        print(f"    错误:  {total_stats['yfdd_errors']}")

    print(f"  耗时: {elapsed / 60:.1f} 分钟")
    print("=" * 60)


if __name__ == "__main__":
    main()
