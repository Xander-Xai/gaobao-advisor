#!/usr/bin/env python3
"""
主采集脚本 — 从百度高考 API 批量导入院校 + 录取分数线
基于已验证的 baidu_gaokao.py 采集器。

用法:
  python scripts/import_baidu_gaokao.py                  # 默认: 3000 所院校 + 头部 80 校的分数线
  python scripts/import_baidu_gaokao.py --schools-only   # 只采集院校列表
  python scripts/import_baidu_gaokao.py --scores-only    # 只采集分数线
  python scripts/import_baidu_gaokao.py --top-n 50       # 只采集头部 50 所的分数线
  python scripts/import_baidu_gaokao.py --reset          # 清空数据库后重建

预计耗时:
- 院校列表（3000+ 所）: ~5 分钟
- 头部 50 校的分数线（每校 20 省 × 3 年 × 2 类 = 120 次请求）: ~30 分钟
"""
import os
import sys
import argparse
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import init_db, get_session
from db.models import School, Major, AdmissionScore, EnrollmentPlan, SubjectRanking
from scrapers.baidu_gaokao import (
    import_schools_to_db,
    import_scores_to_db,
    iter_schools,
    fetch_school_score,
)


def main():
    parser = argparse.ArgumentParser(description="百度高考 API 数据采集")
    parser.add_argument("--reset", action="store_true", help="清空数据库后重建")
    parser.add_argument("--schools-only", action="store_true", help="只采集院校列表")
    parser.add_argument("--scores-only", action="store_true", help="只采集分数线")
    parser.add_argument("--top-n", type=int, default=80, help="分数线采集的院校数（985+头部211）")
    parser.add_argument("--max-schools", type=int, default=None, help="院校列表采集上限")
    parser.add_argument("--provinces", nargs="+", default=None, help="指定采集的省份")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2023, 2022], help="采集的年份")
    args = parser.parse_args()

    print("=" * 60)
    print("  百度高考 API 主采集脚本")
    print("=" * 60)

    # 重置数据库
    if args.reset:
        db_file = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"[重置] 已删除 {db_file}")

    init_db()
    db = get_session()

    try:
        start = time.time()

        # 1. 采集院校列表
        if not args.scores_only:
            print("\n>>> 阶段 1: 采集院校列表")
            school_stats = import_schools_to_db(
                db, School,
                max_schools=args.max_schools,
                skip_existing=True,
            )

        # 2. 采集录取分数线
        if not args.schools_only:
            print("\n>>> 阶段 2: 采集录取分数线")
            # 选择目标学校
            target_schools = db.query(School).filter(
                (School.is_985 == 1) | (School.level == "211")
            ).limit(args.top_n).all()
            print(f"  目标学校: {len(target_schools)} 所")

            score_stats = import_scores_to_db(
                db, School, AdmissionScore,
                schools=target_schools,
                provinces=args.provinces,
                years=args.years,
            )

        # 统计
        elapsed = time.time() - start
        school_count = db.query(School).count()
        score_count = db.query(AdmissionScore).count()
        major_count = db.query(Major).count()

        print("\n" + "=" * 60)
        print("  采集完成")
        print("=" * 60)
        print(f"  院校: {school_count} 条")
        print(f"  专业: {major_count} 条")
        print(f"  录取分数线: {score_count} 条")
        print(f"  耗时: {elapsed/60:.1f} 分钟")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
