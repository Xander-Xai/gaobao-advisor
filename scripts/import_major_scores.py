#!/usr/bin/env python3
"""
专业分数线数据采集脚本 — 从百度高考 API 拉取并写入 admission_scores 表。
专业分数线比院校分数线更详细，包含每个专业的具体录取分数。

API: https://gaokao.baidu.com/gk/gkschool/majorscore

用法:
  python scripts/import_major_scores.py --layer 1          # 双一流院校（默认）
  python scripts/import_major_scores.py --top-n 50          # 前50所院校
  python scripts/import_major_scores.py --provinces ALL     # 30省全覆盖
  python scripts/import_major_scores.py --async              # 异步模式
"""

import argparse
import asyncio
import os
import sys
import time

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db  # noqa: E402
from db.models import AdmissionScore, Major, School  # noqa: E402
from scrapers.baidu_gaokao import BASE_URL, DELAY, HEADERS, PAGE_SIZE  # noqa: E402

ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "陕西", "甘肃", "青海", "宁夏", "新疆",
]

# 省份 → curriculum 映射（与招生计划/分数线API一致）
PROVINCE_CURRICULUMS = {
    "北京": ["3+3综合"], "天津": ["3+3综合"], "上海": ["3+3综合"],
    "山东": ["3+3综合"], "海南": ["3+3综合"], "浙江": ["3+3综合"],
    "广东": ["物理类", "历史类"], "江苏": ["物理类", "历史类"],
    "河北": ["物理类", "历史类"], "辽宁": ["物理类", "历史类"],
    "重庆": ["物理类", "历史类"], "安徽": ["物理类", "历史类"],
    "福建": ["物理类", "历史类"], "湖北": ["物理类", "历史类"],
    "湖南": ["物理类", "历史类"], "广西": ["物理类", "历史类"],
    "江西": ["物理类", "历史类"], "贵州": ["物理类", "历史类"],
    "甘肃": ["物理类", "历史类"], "黑龙江": ["物理类", "历史类"],
    "吉林": ["物理类", "历史类"],
    "四川": ["理科", "文科"], "河南": ["理科", "文科"],
    "山西": ["理科", "文科"], "陕西": ["理科", "文科"],
    "云南": ["理科", "文科"], "内蒙古": ["理科", "文科"],
    "宁夏": ["理科", "文科"], "青海": ["理科", "文科"],
    "新疆": ["理科", "文科"], "西藏": ["理科", "文科"],
}

ASYNC_CONCURRENCY = 5


def safe_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def fetch_major_score_page(school: str, province: str, year: int, page: int = 1) -> list[dict]:
    """获取专业分数线单页"""
    import json
    import urllib.parse
    import urllib.request

    params = {"rn": PAGE_SIZE, "school": school, "province": province, "year": str(year), "pn": page}
    url = f"{BASE_URL}/gk/gkschool/majorscore?" + urllib.parse.urlencode(params)

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if "data" not in data:
                return []
            ms = data["data"].get("major_score", {})
            return ms.get("dataList", [])
        except Exception:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                return []
    return []


async def async_fetch_major_score_page(
    client: httpx.AsyncClient, school: str, province: str, year: int, page: int = 1
) -> list[dict]:
    """异步获取专业分数线单页"""
    params = {"rn": PAGE_SIZE, "school": school, "province": province, "year": str(year), "pn": page}
    import urllib.parse
    url = f"{BASE_URL}/gk/gkschool/majorscore?" + urllib.parse.urlencode(params)

    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "data" not in data:
                return []
            ms = data["data"].get("major_score", {})
            return ms.get("dataList", [])
        except Exception:
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                return []
    return []


def select_schools_by_layers(db, layers: list[int], limit: int = None) -> list:
    """按层级筛选目标学校"""
    result = []
    seen_ids = set()
    if 1 in layers:
        for s in db.query(School).filter(School.is_double_first_class == 1).all():
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)
    if 2 in layers:
        for s in db.query(School).filter(School.is_double_first_class == 0, School.ranking <= 300, School.ranking.isnot(None)).all():
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)
    if 3 in layers:
        for s in db.query(School).filter(
            School.is_double_first_class == 0,
            (School.ranking > 300) | (School.ranking.is_(None)),
            School.school_type != "专科",
        ).all():
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)
    if limit:
        result = result[:limit]
    return result


def import_major_scores(db, school: School, provinces: list[str], years: list[int]) -> dict:
    """为一所学校采集专业分数线"""
    stats = {"new": 0, "skipped": 0, "errors": 0, "requests": 0}

    for province in provinces:
        for year in years:
            # 跳过已有数据
            existing_count = (
                db.query(AdmissionScore)
                .filter(
                    AdmissionScore.school_id == school.id,
                    AdmissionScore.province == province,
                    AdmissionScore.year == year,
                    AdmissionScore.major_id.isnot(None),
                )
                .count()
            )
            if existing_count > 50:  # 已有足够专业数据
                stats["skipped"] += 1
                continue

            try:
                page = 1
                all_items = []
                while True:
                    items = fetch_major_score_page(school.name, province, year, page)
                    stats["requests"] += 1
                    if not items:
                        break
                    all_items.extend(items)
                    if len(items) < PAGE_SIZE:
                        break
                    page += 1
                    time.sleep(DELAY)

                if not all_items:
                    time.sleep(DELAY / 2)
                    continue

                batch_added = 0
                for item in all_items:
                    major_name = item.get("majorName", "").strip()
                    if not major_name:
                        continue
                    # 查找专业
                    major = db.query(Major).filter(Major.name == major_name).first()
                    if not major:
                        continue

                    min_score = safe_int(item.get("minScore"))
                    min_rank = safe_int(item.get("minScoreOrder"))
                    avg_score = safe_int(item.get("avgScore"))

                    existing = (
                        db.query(AdmissionScore)
                        .filter(
                            AdmissionScore.school_id == school.id,
                            AdmissionScore.major_id == major.id,
                            AdmissionScore.province == province,
                            AdmissionScore.year == year,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    rec = AdmissionScore(
                        school_id=school.id,
                        major_id=major.id,
                        province=province,
                        year=year,
                        batch=item.get("batchName", "本科批"),
                        subject_type="综合",
                        min_score=min_score,
                        avg_score=avg_score,
                        min_rank=min_rank,
                    )
                    db.add(rec)
                    batch_added += 1
                    stats["new"] += 1

                if batch_added > 0:
                    db.commit()

            except Exception:
                stats["errors"] += 1
                try:
                    db.rollback()
                except Exception:
                    pass

    return stats


async def async_import_major_scores(
    db, school: School, provinces: list[str], years: list[int], semaphore: asyncio.Semaphore, stats: dict
) -> int:
    """异步采集专业分数线"""
    school_new = 0

    async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
        for province in provinces:
            for year in years:
                async with semaphore:
                    existing_count = (
                        db.query(AdmissionScore)
                        .filter(
                            AdmissionScore.school_id == school.id,
                            AdmissionScore.province == province,
                            AdmissionScore.year == year,
                            AdmissionScore.major_id.isnot(None),
                        )
                        .count()
                    )
                    if existing_count > 50:
                        continue

                    try:
                        page = 1
                        all_items = []
                        while True:
                            items = await async_fetch_major_score_page(client, school.name, province, year, page)
                            stats["requests"] += 1
                            if not items:
                                break
                            all_items.extend(items)
                            if len(items) < PAGE_SIZE:
                                break
                            page += 1

                        if not all_items:
                            continue

                        for item in all_items:
                            major_name = item.get("majorName", "").strip()
                            if not major_name:
                                continue
                            major = db.query(Major).filter(Major.name == major_name).first()
                            if not major:
                                continue
                            existing = (
                                db.query(AdmissionScore)
                                .filter(
                                    AdmissionScore.school_id == school.id,
                                    AdmissionScore.major_id == major.id,
                                    AdmissionScore.province == province,
                                    AdmissionScore.year == year,
                                )
                                .first()
                            )
                            if existing:
                                continue

                            rec = AdmissionScore(
                                school_id=school.id,
                                major_id=major.id,
                                province=province,
                                year=year,
                                batch=item.get("batchName", "本科批"),
                                subject_type="综合",
                                min_score=safe_int(item.get("minScore")),
                                avg_score=safe_int(item.get("avgScore")),
                                min_rank=safe_int(item.get("minScoreOrder")),
                            )
                            db.add(rec)
                            school_new += 1

                        db.commit()
                    except Exception:
                        stats["errors"] += 1
                        try:
                            db.rollback()
                        except Exception:
                            pass

    return school_new


def main():
    parser = argparse.ArgumentParser(description="专业分数线采集")
    parser.add_argument("--layer", type=str, default="1", help="院校层级: 1,2,3")
    parser.add_argument("--top-n", type=int, default=None, help="院校上限")
    parser.add_argument("--provinces", nargs="+", default=None)
    parser.add_argument("--years", nargs="+", type=int, default=[2024], help="指定年份")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="异步模式")
    args = parser.parse_args()

    layers = [int(x.strip()) for x in args.layer.split(",")]
    provinces = args.provinces or ALL_PROVINCES[:5]  # 默认前5省

    init_db()
    db = get_session()

    try:
        start_time = time.time()
        target = select_schools_by_layers(db, layers, limit=args.top_n)
        print(f"目标: {len(target)} 校 × {len(provinces)} 省 × {len(args.years)} 年")

        total_new = 0
        if args.async_mode:
            print("  模式: 异步并行")
            stats = {"requests": 0, "errors": 0}
            semaphore = asyncio.Semaphore(ASYNC_CONCURRENCY)

            async def run_all():
                nonlocal total_new
                for idx, school in enumerate(target):
                    added = await async_import_major_scores(db, school, provinces, args.years, semaphore, stats)
                    total_new += added
                    print(f"  [{idx+1}/{len(target)}] {school.name}: +{added} (总计 {total_new})")

            asyncio.run(run_all())
        else:
            for idx, school in enumerate(target):
                stats = import_major_scores(db, school, provinces, args.years)
                total_new += stats["new"]
                print(f"  [{idx+1}/{len(target)}] {school.name}: +{stats['new']} (总计 {total_new})")

        elapsed = time.time() - start_time
        total = db.query(AdmissionScore).filter(AdmissionScore.major_id.isnot(None)).count()

        print("\n" + "=" * 60)
        print("  专业分数线采集完成")
        print(f"  新增: {total_new} 条")
        print(f"  数据库中总计: {total} 条")
        print(f"  耗时: {elapsed/60:.1f} 分钟")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
