#!/usr/bin/env python3
"""
采集2025年缺失省份录取数据 — 使用无 curriculum 参数的 API 请求。
解决传统文理分科省份的 2025 年数据缺失问题。

原因: 百度高考 API 的 schoolscore 端点当指定 curriculum 参数时，
对传统文理分科省份（四川/河南/山西/陕西/云南/青海/内蒙古/宁夏）返回空。
不指定 curriculum 参数时，API 自动匹配正确的科类。

用法:
  python scripts/import_2025_missing_provinces.py
"""

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

MISSING_PROVINCES = ["四川", "河南", "山西", "陕西", "云南", "青海", "内蒙古", "宁夏"]
BASE_URL = "https://gaokao.baidu.com/gk/gkschool/schoolscore"
DELAY = 0.3


def fetch_scores_no_curriculum(school_name: str, province: str, year: int = 2025) -> list[dict]:
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
                print(f"    [WARN] {school_name}: {e}")
                return []
    return []


def safe_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def main():
    print("=" * 60)
    print("  2025年缺失省份录取数据采集")
    print("  使用无curriculum参数模式")
    print("=" * 60)

    init_db()
    db = get_session()

    try:
        total_new = 0
        total_skipped = 0
        total_errors = 0

        for province in MISSING_PROVINCES:
            print(f"\n[{province}] 开始采集...")

            # 获取该省所有学校
            schools = (
                db.query(School)
                .filter(School.province == province)
                .order_by(School.is_double_first_class.desc(), School.ranking)
                .all()
            )
            print(f"  共 {len(schools)} 所学校")

            prov_new = 0
            prov_skipped = 0

            for idx, school in enumerate(schools):
                # 跳过已有2025年数据
                existing = (
                    db.query(AdmissionScore)
                    .filter(
                        AdmissionScore.school_id == school.id,
                        AdmissionScore.province == province,
                        AdmissionScore.year == 2025,
                    )
                    .count()
                )
                if existing > 0:
                    prov_skipped += 1
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

                    exists = (
                        db.query(AdmissionScore)
                        .filter(
                            AdmissionScore.school_id == school.id,
                            AdmissionScore.province == province,
                            AdmissionScore.year == 2025,
                            AdmissionScore.batch == batch_name,
                            AdmissionScore.subject_type == subject_type,
                            AdmissionScore.major_id.is_(None),
                        )
                        .first()
                    )
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

                print(f"  [{idx + 1}/{len(schools)}] {school.name}: +{school_new}", end="", flush=True)
                if (idx + 1) % 20 == 0:
                    print()
                else:
                    print(" ", end="", flush=True)

            print(f"\n  [{province}] 新增 {prov_new} / 跳过 {prov_skipped}")

        # 统计
        p2025 = db.execute("SELECT COUNT(DISTINCT province) FROM admission_scores WHERE year=2025").scalar()
        print(f"\n{'=' * 60}")
        print("  采集完成！")
        print(f"  新增 2025 年录取数据: {total_new} 条")
        print(f"  2025年覆盖省份: {p2025}/30")
        print(f"{'=' * 60}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
