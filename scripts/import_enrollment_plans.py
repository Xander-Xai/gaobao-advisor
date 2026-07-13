#!/usr/bin/env python3
"""
招生计划数据采集脚本 — 从百度高考 API 拉取并写入 enrollment_plans 表。

功能:
  1. 支持按 (校, 省, 年) 采集招生计划
  2. 自动 curriculum 映射（3+3综合/物理类+历史类/理科+文科）
  3. 幂等去重（基于 UniqueConstraint）
  4. 断点续传
  5. 异步并行模式（更快）

用法:
  python scripts/import_enrollment_plans.py --layer 1,2            # L1+L2 院校（默认）
  python scripts/import_enrollment_plans.py --layer 1,2,3          # L1+L2+L3
  python scripts/import_enrollment_plans.py --full                  # 全部院校
  python scripts/import_enrollment_plans.py --top-n 100             # 前100所院校
  python scripts/import_enrollment_plans.py --provinces ALL         # 30省全覆盖
  python scripts/import_enrollment_plans.py --years 2024           # 指定年份
  python scripts/import_enrollment_plans.py --async                 # 异步模式（更快）
  python scripts/import_enrollment_plans.py --resume                # 断点续传
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
from db.models import EnrollmentPlan, School  # noqa: E402
from scrapers.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402

# ── 院校层级筛选参数 ──
LAYER_FILTERS = {
    1: "双一流",
    2: "省属重点",
    3: "一般本科",
    4: "专科/职业",
}

# curriculum 映射：参考百度 API 的省份 → curriculum 参数规则
# 招生计划 API 与分数线 API 使用相同的 curriculum 参数
PROVINCE_CURRICULUM = {
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
    # 西藏：传统文理
    "西藏": ["理科", "文科"],
}

ALL_PROVINCES = list(PROVINCE_CURRICULUM.keys())

# API 配置
BASE_URL = "https://gaokao.baidu.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://gaokao.baidu.com/",
}
DELAY = 0.2  # 请求间隔秒数
PAGE_SIZE = 50
ASYNC_CONCURRENCY = 5


def fetch_plan_page(school: str, province: str, year: int, curriculum: str, page: int = 1) -> list[dict]:
    """获取招生计划单页数据"""
    import json
    import urllib.parse
    import urllib.request

    params = {
        "curriculum": curriculum,
        "school": school,
        "province": province,
        "year": str(year),
        "pn": page,
        "rn": PAGE_SIZE,
    }
    url = f"{BASE_URL}/gk/gkschool/getrecruitingscheme?" + urllib.parse.urlencode(params)

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if "data" not in data:
                return []
            items = data["data"].get("list", [])
            return items
        except Exception:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                return []
    return []


async def async_fetch_plan_page(
    client: httpx.AsyncClient, school: str, province: str, year: int, curriculum: str, page: int = 1
) -> list[dict]:
    """异步获取招生计划单页数据"""
    params = {
        "curriculum": curriculum,
        "school": school,
        "province": province,
        "year": str(year),
        "pn": page,
        "rn": PAGE_SIZE,
    }
    import urllib.parse

    url = f"{BASE_URL}/gk/gkschool/getrecruitingscheme?" + urllib.parse.urlencode(params)

    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "data" not in data:
                return []
            return data["data"].get("list", [])
        except Exception:
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                return []
    return []


def safe_int(v) -> int | None:
    """安全转整数"""
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def parse_tuition(tuition_str: str) -> int | None:
    """解析学费字符串，如 '5850元' → 5850"""
    if not tuition_str:
        return None
    cleaned = tuition_str.replace("元", "").replace("元/年", "").replace(",", "").strip()
    return safe_int(cleaned)


def parse_duration(duration_str: str) -> int | None:
    """解析学制字符串，如 '4年' → 4"""
    if not duration_str:
        return None
    cleaned = duration_str.replace("年", "").strip()
    return safe_int(cleaned)


def select_schools_by_layers(db, layers: list[int], limit: int = None) -> list:
    """按层级筛选目标学校"""
    result = []
    seen_ids = set()

    if 1 in layers:
        layer1 = db.query(School).filter(School.is_double_first_class == 1).all()
        for s in layer1:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if 2 in layers:
        layer2 = (
            db.query(School)
            .filter(
                School.is_double_first_class == 0,
                School.ranking <= 300,
                School.ranking.isnot(None),
            )
            .all()
        )
        for s in layer2:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if 3 in layers:
        layer3 = (
            db.query(School)
            .filter(
                School.is_double_first_class == 0,
                (School.ranking > 300) | (School.ranking.is_(None)),
                School.school_type != "专科",
            )
            .all()
        )
        for s in layer3:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if 4 in layers:
        layer4 = db.query(School).filter(School.school_type.like("%专科%")).all()
        for s in layer4:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if limit:
        result = result[:limit]

    print(
        f"  层级筛选: L1={sum(1 for s in result if s.is_double_first_class)} "
        f"L2={sum(1 for s in result if not s.is_double_first_class and s.ranking and s.ranking <= 300)} "
        f"L3={sum(1 for s in result if not s.is_double_first_class and (not s.ranking or s.ranking > 300) and s.school_type != '专科')} "
        f"L4={sum(1 for s in result if not s.is_double_first_class and s.school_type == '专科')} "
        f"→ 总计 {len(result)} 校"
    )
    return result


def import_plans_for_school(db, school: School, provinces: list[str], years: list[int]) -> dict:
    """为一所学校采集所有 (省, 年) 组合的招生计划。返回统计。"""
    stats = {"new": 0, "skipped": 0, "errors": 0, "requests": 0}

    for province in provinces:
        curriculums = PROVINCE_CURRICULUM.get(province, ["物理类", "历史类"])
        for year in years:
            for curriculum in curriculums:
                # 跳过已有数据
                existing_count = (
                    db.query(EnrollmentPlan)
                    .filter(
                        EnrollmentPlan.school_id == school.id,
                        EnrollmentPlan.province == province,
                        EnrollmentPlan.year == year,
                        EnrollmentPlan.subject_type == curriculum,
                    )
                    .count()
                )
                if existing_count > 0:
                    stats["skipped"] += 1
                    continue

                try:
                    # 分页获取
                    page = 1
                    all_items = []
                    while True:
                        items = fetch_plan_page(school.name, province, year, curriculum, page)
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

                    # 写入数据库
                    seen_majors = set()  # 去重辅助
                    batch_added = 0
                    for item in all_items:
                        major_name = item.get("major_name", "").strip()
                        if not major_name:
                            continue
                        dedup_key = (major_name, curriculum, item.get("batch_name", "本科批"))
                        if dedup_key in seen_majors:
                            continue
                        seen_majors.add(dedup_key)

                        plan_count = safe_int(item.get("enroll_num"))
                        tuition = parse_tuition(item.get("tuition"))
                        duration = parse_duration(item.get("lengthOfSchooling"))
                        batch = item.get("batch_name", "本科批")
                        subject_req = item.get("selectSubjects", "")

                        existing = (
                            db.query(EnrollmentPlan)
                            .filter(
                                EnrollmentPlan.school_id == school.id,
                                EnrollmentPlan.province == province,
                                EnrollmentPlan.year == year,
                                EnrollmentPlan.batch == batch,
                            )
                            .first()
                        )
                        if existing:
                            continue

                        # 查找或创建 major
                        major_id = None
                        major = db.query(Major).filter(Major.name == major_name).first()
                        if major:
                            major_id = major.id

                        rec = EnrollmentPlan(
                            school_id=school.id,
                            major_id=major_id,
                            province=province,
                            year=year,
                            plan_count=plan_count,
                            subject_requirement=subject_req,
                            batch=batch,
                            duration=duration,
                            tuition=tuition,
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


async def async_import_plans_for_school(
    client: httpx.AsyncClient,
    db,
    school: School,
    provinces: list[str],
    years: list[int],
    semaphore: asyncio.Semaphore,
    stats: dict,
) -> int:
    """异步版：为一所学校采集招生计划"""
    school_new = 0

    for province in provinces:
        curriculums = PROVINCE_CURRICULUM.get(province, ["物理类", "历史类"])
        for year in years:
            for curriculum in curriculums:
                async with semaphore:
                    existing_count = (
                        db.query(EnrollmentPlan)
                        .filter(
                            EnrollmentPlan.school_id == school.id,
                            EnrollmentPlan.province == province,
                            EnrollmentPlan.year == year,
                            EnrollmentPlan.subject_type == curriculum,
                        )
                        .count()
                    )
                    if existing_count > 0:
                        continue

                    try:
                        page = 1
                        all_items = []
                        while True:
                            items = await async_fetch_plan_page(client, school.name, province, year, curriculum, page)
                            stats["requests"] += 1
                            if not items:
                                break
                            all_items.extend(items)
                            if len(items) < PAGE_SIZE:
                                break
                            page += 1
                            await asyncio.sleep(DELAY)

                        if not all_items:
                            continue

                        seen_majors = set()
                        for item in all_items:
                            major_name = item.get("major_name", "").strip()
                            if not major_name:
                                continue
                            dedup_key = (major_name, curriculum, item.get("batch_name", "本科批"))
                            if dedup_key in seen_majors:
                                continue
                            seen_majors.add(dedup_key)

                            major = db.query(Major).filter(Major.name == major_name).first()
                            rec = EnrollmentPlan(
                                school_id=school.id,
                                major_id=major.id if major else None,
                                province=province,
                                year=year,
                                plan_count=safe_int(item.get("enroll_num")),
                                subject_requirement=item.get("selectSubjects", ""),
                                batch=item.get("batch_name", "本科批"),
                                duration=parse_duration(item.get("lengthOfSchooling")),
                                tuition=parse_tuition(item.get("tuition")),
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
    parser = argparse.ArgumentParser(description="招生计划采集脚本")
    parser.add_argument("--full", action="store_true", help="全量模式（= --layer 1,2,3,4）")
    parser.add_argument("--layer", type=str, default=None, help="院校层级: 1,2,3,4")
    parser.add_argument("--top-n", type=int, default=None, help="院校上限")
    parser.add_argument("--provinces", nargs="+", default=None, help="指定省份或 ALL")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025], help="采集年份")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    parser.add_argument("--checkpoint", type=str, default="data/checkpoint_plans.json", help="断点文件路径")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="异步模式")
    args = parser.parse_args()

    # 解析省份
    if args.provinces and args.provinces[0].upper() == "ALL":
        provinces = ALL_PROVINCES
    elif args.provinces:
        provinces = args.provinces
    else:
        provinces = None  # 默认 30 省

    # 解析层级
    if args.full:
        layers = [1, 2, 3, 4]
    elif args.layer:
        layers = [int(x.strip()) for x in args.layer.split(",")]
    else:
        layers = [1, 2]  # 默认 L1 + L2

    init_db()
    db = get_session()

    try:
        start_time = time.time()

        # 选择目标学校
        target = select_schools_by_layers(db, layers, limit=args.top_n)
        if not target:
            print("[ERROR] 无目标学校，请先运行院校列表采集")
            return

        # 断点续传
        start_index = 0
        if args.resume:
            ckpt = load_checkpoint(args.checkpoint)
            if ckpt:
                start_index = min(ckpt.get("school_index", 0), len(target))
                print(f"  [续传] 从第 {start_index} 校继续")
                target = target[start_index:]

        # 确定省份
        if provinces is None:
            # 从学校数据中提取省份
            school_provinces = set()
            for s in target:
                if s.province:
                    school_provinces.add(s.province)
            provinces = list(school_provinces)
            print(f"  自动识别 {len(provinces)} 个相关省份")

        print(f"  目标: {len(target)} 校 × {len(provinces)} 省 × {len(args.years)} 年")

        total_new = 0
        total_errors = 0

        if args.async_mode:
            print("  模式: 异步并行")
            stats = {"requests": 0, "errors": 0}
            semaphore = asyncio.Semaphore(ASYNC_CONCURRENCY)

            async def run_async():
                nonlocal total_new, total_errors
                async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
                    for idx, school in enumerate(target):
                        actual_idx = start_index + idx
                        added = await async_import_plans_for_school(
                            client, db, school, provinces, args.years, semaphore, stats
                        )
                        total_new += added

                        if (idx + 1) % 10 == 0:
                            save_checkpoint(
                                args.checkpoint,
                                {
                                    "school_index": actual_idx + 1,
                                    "total_schools": len(target),
                                    "current_school": school.name,
                                    "stats": stats,
                                },
                            )

                        print(f"  [{actual_idx + 1}/{len(target)}] {school.name}: +{added} 条 (总计 {total_new})")

            asyncio.run(run_async())
            total_errors = stats["errors"]
        else:
            for idx, school in enumerate(target):
                actual_idx = start_index + idx
                stats = import_plans_for_school(db, school, provinces, args.years)
                total_new += stats["new"]
                total_errors += stats["errors"]

                if (idx + 1) % 10 == 0:
                    save_checkpoint(
                        args.checkpoint,
                        {
                            "school_index": actual_idx + 1,
                            "total_schools": len(target),
                            "current_school": school.name,
                        },
                    )

                print(f"  [{actual_idx + 1}/{len(target)}] {school.name}: +{stats['new']} 条 (总计 {total_new})")

        elapsed = time.time() - start_time
        total_in_db = db.query(EnrollmentPlan).count()

        print("\n" + "=" * 60)
        print("  招生计划采集完成")
        print("=" * 60)
        print(f"  本次新增: {total_new} 条")
        print(f"  错误: {total_errors}")
        print(f"  数据库中总计: {total_in_db} 条")
        print(f"  耗时: {elapsed / 60:.1f} 分钟")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    from db.models import Major

    main()
