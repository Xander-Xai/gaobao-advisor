#!/usr/bin/env python3
"""
修复2025年9省录取数据严重不足的问题。

问题: 河南/四川/陕西/云南/内蒙古/山西/宁夏/西藏/青海 的2025年数据
      仅为2024年的4%-30%。

根因: 传统文理分科省份指定 curriculum 参数时 API 返回空，
      不指定时 API 自动匹配正确科类。

策略:
1. 对9省全部学校，不带 curriculum 参数重新请求 API
2. 采集所有其他省学校在9省的招生数据（不仅限本省学校）
3. 采集前后对比数据量，目标: 2025年 ≥ 2024年的80%

用法:
  python scripts/fix_2025_provinces.py
  python scripts/fix_2025_provinces.py --province 河南
  python scripts/fix_2025_provinces.py --dry-run
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db
from db.models import AdmissionScore, School

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://gaokao.baidu.com/",
}

MISSING_PROVINCES = ['河南', '四川', '陕西', '云南', '内蒙古', '山西', '宁夏', '青海', '西藏']
BASE_URL = "https://gaokao.baidu.com/gk/gkschool/schoolscore"
DELAY = 0.3


def safe_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def get_2024_count(db, province):
    """获取某省2024年数据量作为基线"""
    return db.query(AdmissionScore).filter(
        AdmissionScore.province == province,
        AdmissionScore.year == 2024
    ).count()


def fetch_scores_no_curriculum(school_name, province, year=2025):
    """不指定 curriculum，获取学校录取分数线"""
    params = {"school": school_name, "province": province, "year": str(year)}
    url = f"{BASE_URL}?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if "data" not in data:
                return []
            sd = data["data"].get("school_score", {})
            return sd.get("dataList", [])
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                return []
    return []


def fix_province(db, province, dry_run=False, force=False):
    """修复单个省份的2025年数据"""
    count_2024 = get_2024_count(db, province)
    count_2025_before = db.query(AdmissionScore).filter(
        AdmissionScore.province == province, AdmissionScore.year == 2025
    ).count()

    if dry_run:
        print(f"  [{province}] 2024: {count_2024:,} | 2025(当前): {count_2025_before:,} | 目标: {int(count_2024*0.8):,}")
        return 0

    # 获取所有学校（不限于该省学校），按重要性排序
    schools = (
        db.query(School)
        .order_by(School.is_double_first_class.desc(), School.ranking.asc().nulls_last())
        .all()
    )

    total_new = 0
    total_skipped = 0

    for idx, school in enumerate(schools):
        if not force:
            existing = db.query(AdmissionScore).filter(
                AdmissionScore.school_id == school.id,
                AdmissionScore.province == province,
                AdmissionScore.year == 2025,
            ).count()
            if existing > 0:
                total_skipped += 1
                continue

        scores = fetch_scores_no_curriculum(school.name, province, 2025)
        time.sleep(DELAY)

        if not scores:
            continue

        school_new = 0
        seen_keys = set()

        for s in scores:
            min_score = safe_int(s.get("minScore"))
            if min_score is None:
                continue
            batch_name = s.get("batchName", "本科批")
            subject_type = s.get("subjectType") or s.get("curriculum") or "综合"
            dedup_key = (batch_name, subject_type, min_score)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            min_rank = safe_int(s.get("minScoreOrder"))

            exists = db.query(AdmissionScore).filter(
                AdmissionScore.school_id == school.id,
                AdmissionScore.province == province,
                AdmissionScore.year == 2025,
                AdmissionScore.batch == batch_name,
                AdmissionScore.subject_type == subject_type,
                AdmissionScore.major_id.is_(None),
            ).first()
            if exists:
                continue

            rec = AdmissionScore(
                school_id=school.id,
                major_id=None,
                province=province,
                year=2025,
                batch=batch_name,
                subject_type=subject_type,
                min_score=min_score,
                min_rank=min_rank,
                plan_count=safe_int(s.get("enrollNum")),
            )
            db.add(rec)
            school_new += 1
            total_new += 1

        if school_new > 0:
            db.commit()

        if (idx + 1) % 100 == 0:
            count_now = db.query(AdmissionScore).filter(
                AdmissionScore.province == province, AdmissionScore.year == 2025
            ).count()
            print(f"  [{province}] {idx+1}/{len(schools)} 校 | 新增 {total_new} | 当前 {count_now:,}/{count_2024:,}")

    count_2025_after = db.query(AdmissionScore).filter(
        AdmissionScore.province == province, AdmissionScore.year == 2025
    ).count()
    ratio = count_2025_after / count_2024 * 100 if count_2024 > 0 else 0
    status = "✅" if ratio >= 80 else "⚠️"
    print(f"  [{province}] 完成: {count_2025_before:,} → {count_2025_after:,} (目标{count_2024*80//100:,}, 实际{ratio:.0f}%) {status}")

    return total_new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--province", type=str, default=None, help="只修复指定省份")
    parser.add_argument("--dry-run", action="store_true", help="只显示当前状态，不采集")
    parser.add_argument("--force", action="store_true", help="跳过跳过检查，强制补采所有学校的更多批次数据")
    args = parser.parse_args()

    print("=" * 60)
    print("  2025年9省数据修复")
    print("=" * 60)

    init_db()
    db = get_session()

    try:
        provinces = [args.province] if args.province else MISSING_PROVINCES

        print("\n--- 修复前状态 ---")
        for p in provinces:
            c24 = get_2024_count(db, p)
            c25 = db.query(AdmissionScore).filter(AdmissionScore.province == p, AdmissionScore.year == 2025).count()
            ratio = c25 / c24 * 100 if c24 > 0 else 0
            print(f"  {p}: 2024={c24:,} | 2025={c25:,} ({ratio:.0f}%)")

        if args.dry_run:
            print("\n[dry-run] 不执行采集")
            db.close()
            return

        total_new = 0
        for p in provinces:
            print(f"\n>>> 修复 {p}...")
            total_new += fix_province(db, p, force=args.force)

        print("\n--- 修复后状态 ---")
        for p in provinces:
            c24 = get_2024_count(db, p)
            c25 = db.query(AdmissionScore).filter(AdmissionScore.province == p, AdmissionScore.year == 2025).count()
            ratio = c25 / c24 * 100 if c24 > 0 else 0
            status = "✅" if ratio >= 80 else "⚠️"
            print(f"  {p}: 2024={c24:,} | 2025={c25:,} ({ratio:.0f}%) {status}")

        print(f"\n总计新增: {total_new:,} 条")

    finally:
        db.close()


if __name__ == "__main__":
    main()