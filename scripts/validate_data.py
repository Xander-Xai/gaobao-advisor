#!/usr/bin/env python3
"""
数据质量验证脚本 — 导入完成后运行，检查数据完整性。
用法: python scripts/validate_data.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import func  # noqa: E402

from db.database import get_session, init_db  # noqa: E402
from db.models import AdmissionScore, School  # noqa: E402
from scrapers.provinces import ALL_PROVINCES  # noqa: E402


def validate() -> None:
    init_db()
    db = get_session()

    print("=" * 60)
    print("  数据质量验证报告")
    print("=" * 60)

    # 1. 总体统计
    total_schools = db.query(School).count()
    total_scores = db.query(AdmissionScore).count()
    schools_with_scores = db.query(AdmissionScore.school_id).distinct().count()

    print("\n总体统计:")
    print(f"  院校总数: {total_schools}")
    print(f"  录取分数记录: {total_scores}")
    if total_schools:
        coverage = schools_with_scores / total_schools * 100
        print(f"  有分数数据的院校: {schools_with_scores}/{total_schools} ({coverage:.1f}%)")
    else:
        print("  有分数数据的院校: 0/0 (n/a — 数据库中没有任何院校记录，无法计算覆盖率)")

    # 2. 省份覆盖
    print("\n省份覆盖:")
    province_stats = (
        db.query(AdmissionScore.province, func.count(AdmissionScore.id))
        .group_by(AdmissionScore.province)
        .order_by(func.count(AdmissionScore.id).desc())
        .all()
    )

    provinces_with_data = set(p for p, _ in province_stats)
    missing_provinces = set(ALL_PROVINCES) - provinces_with_data

    for p, c in province_stats:
        print(f"  {p}: {c:,} 条")

    if missing_provinces:
        print(f"\n  WARNING: 缺失省份: {', '.join(sorted(missing_provinces))}")
    else:
        print(f"\n  OK: 全部 {len(ALL_PROVINCES)} 省覆盖")

    # 3. 年份覆盖
    print("\n年份覆盖:")
    year_stats = (
        db.query(AdmissionScore.year, func.count(AdmissionScore.id))
        .group_by(AdmissionScore.year)
        .order_by(AdmissionScore.year.desc())
        .all()
    )

    for y, c in year_stats:
        print(f"  {y}: {c:,} 条")

    # 4. 数据质量检查
    print("\n数据质量:")

    # 分数范围 — 海南省使用标准分制度（满分900），分数 >750 是正常的
    # 阈值说明：
    #   - < 60：真正的异常（无分数线低于60）
    #   - 60-99：专科批/提前批综合评估招生的合法低分（天津专科、昆山杜克大学等）
    bad_scores = (
        db.query(AdmissionScore)
        .filter(
            (AdmissionScore.min_score < 60) | ((AdmissionScore.min_score > 750) & (AdmissionScore.province != "海南"))
        )
        .count()
    )
    print(f"  异常分数（<60 或 >750，海南除外）: {bad_scores}")

    # 位次范围
    bad_ranks = db.query(AdmissionScore).filter(AdmissionScore.min_rank < 0).count()
    print(f"  负数位次: {bad_ranks}")

    # 空分数
    null_scores = db.query(AdmissionScore).filter(AdmissionScore.min_score.is_(None)).count()
    print(f"  空分数记录: {null_scores}")

    # 5. 批次分布
    print("\n批次分布:")
    batch_stats = (
        db.query(AdmissionScore.batch, func.count(AdmissionScore.id))
        .group_by(AdmissionScore.batch)
        .order_by(func.count(AdmissionScore.id).desc())
        .limit(10)
        .all()
    )

    for b, c in batch_stats:
        print(f"  {b}: {c:,} 条")

    # 6. 结论
    print("\n" + "=" * 60)
    issues = []
    if missing_provinces:
        issues.append(f"缺失 {len(missing_provinces)} 个省份")
    if bad_scores > 0:
        issues.append(f"{bad_scores} 条异常分数")
    if bad_ranks > 0:
        issues.append(f"{bad_ranks} 条负数位次")

    if issues:
        print(f"  WARNING: 发现问题: {'; '.join(issues)}")
    else:
        print("  OK: 数据质量验证通过")

    print("=" * 60)
    db.close()


if __name__ == "__main__":
    validate()
