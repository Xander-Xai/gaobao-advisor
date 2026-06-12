#!/usr/bin/env python3
"""
百度高考 API 主采集脚本 v2 — 支持分层 + 断点续传 + 30 省全覆盖

用法:
  python scripts/import_baidu_gaokao.py                           # 默认: 头部 80 校 + 10 省
  python scripts/import_baidu_gaokao.py --schools-only            # 只采集院校列表（补全信息）
  python scripts/import_baidu_gaokao.py --scores-only             # 只采集分数线
  python scripts/import_baidu_gaokao.py --layer 1                 # 只采集双一流（~147 校）
  python scripts/import_baidu_gaokao.py --layer 1,2               # 双一流 + 省属重点（~350 校）
  python scripts/import_baidu_gaokao.py --layer 1,2,3,4           # 全部院校
  python scripts/import_baidu_gaokao.py --full                    # 同 --layer 1,2,3,4
  python scripts/import_baidu_gaokao.py --provinces ALL           # 30 省全覆盖
  python scripts/import_baidu_gaokao.py --resume                  # 从上次断点继续
  python scripts/import_baidu_gaokao.py --reset                   # 清空数据库后重建

预计耗时:
- 院校列表（3000+ 所）: ~10 分钟
- 头部 80 校 × 10 省 × 3 年: ~25 分钟
- 双一流 147 校 × 30 省 × 3 年: ~90 分钟
- 全量 3000 校 × 30 省 × 3 年: ~20 小时（建议 --resume 分批运行）
"""
import argparse
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db
from db.models import AdmissionScore, Major, School
from scrapers.baidu_gaokao import (
    import_schools_to_db,
    import_scores_to_db,
)
from scrapers.checkpoint import clear_checkpoint, load_checkpoint
from scrapers.provinces import ALL_PROVINCES

# ── 院校层级筛选参数 ──
LAYER_FILTERS = {
    1: "双一流",   # is_double_first_class == 1
    2: "省属重点",  # ranking <= 300 且非双一流
    3: "一般本科",  # school_type != '专科' 且非双一流/省重点
    4: "专科/职业",  # school_type == '专科'
}


def select_schools_by_layers(db, layers: list[int], limit: int = None) -> list:
    """按层级筛选目标学校"""
    layer4 = []
    layer1 = []
    layer2 = []
    layer3 = []

    if 4 in layers:
        layer4 = db.query(School).filter(School.school_type == "专科").all()

    if 1 in layers:
        layer1 = db.query(School).filter(School.is_double_first_class == 1).all()

    if 2 in layers:
        layer2 = db.query(School).filter(
            School.is_double_first_class == 0,
            School.ranking <= 300,
            School.ranking.isnot(None),
        ).all()

    if 3 in layers:
        layer3 = db.query(School).filter(
            School.is_double_first_class == 0,
            (School.ranking > 300) | (School.ranking.is_(None)),
            School.school_type != "专科",
        ).all()

    # 按层级顺序合并，去重
    seen_ids = set()
    result = []
    for school_list in [layer1, layer2, layer3, layer4]:
        for s in school_list:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if limit:
        result = result[:limit]

    print(f"  层级筛选: L1={len(layer1)} L2={len(layer2)} L3={len(layer3)} L4={len(layer4)} → 总计 {len(result)} 校")
    return result


def main():
    parser = argparse.ArgumentParser(description="百度高考 API 主采集脚本 v2")
    parser.add_argument("--reset", action="store_true", help="清空数据库后重建")
    parser.add_argument("--schools-only", action="store_true", help="只采集院校列表")
    parser.add_argument("--scores-only", action="store_true", help="只采集分数线")
    parser.add_argument("--full", action="store_true", help="全量模式（= --layer 1,2,3,4）")
    parser.add_argument("--layer", type=str, default=None,
                        help="院校层级，逗号分隔: 1=双一流 2=省属重点 3=一般本科 4=专科")
    parser.add_argument("--top-n", type=int, default=80,
                        help="分数线采集的院校上限")
    parser.add_argument("--max-schools", type=int, default=None,
                        help="院校列表采集上限")
    parser.add_argument("--provinces", nargs="+", default=None,
                        help="指定省份，或 ALL 表示 30 省全覆盖")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2023, 2022],
                        help="采集的年份")
    parser.add_argument("--resume", action="store_true",
                        help="从上次断点继续")
    parser.add_argument("--checkpoint", type=str, default="data/import_checkpoint.json",
                        help="断点文件路径（默认 data/import_checkpoint.json）")
    args = parser.parse_args()

    print("=" * 60)
    print("  百度高考 API 主采集脚本 v2")
    print("=" * 60)

    # 解析省份
    if args.provinces and args.provinces[0].upper() == "ALL":
        provinces = ALL_PROVINCES
    elif args.provinces:
        provinces = args.provinces
    else:
        provinces = None  # 函数内部默认

    # 解析层级
    if args.full:
        layers = [1, 2, 3, 4]
    elif args.layer:
        layers = [int(x.strip()) for x in args.layer.split(",")]
    else:
        layers = None

    # 重置数据库
    if args.reset:
        db_file = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"[重置] 已删除 {db_file}")
        clear_checkpoint(args.checkpoint)

    init_db()
    db = get_session()

    try:
        start = time.time()

        # 1. 采集院校列表（补全信息）
        if not args.scores_only:
            print("\n>>> 阶段 1: 采集院校列表（补全基础信息）")
            school_stats = import_schools_to_db(
                db, School,
                max_schools=args.max_schools,
                skip_existing=True,
            )

        # 2. 采集录取分数线
        if not args.schools_only:
            print("\n>>> 阶段 2: 采集录取分数线")

            # 断点续传
            start_index = 0
            if args.resume:
                ckpt = load_checkpoint(args.checkpoint)
                if ckpt:
                    start_index = ckpt.get("school_index", 0)
                    print(f"  [续传] 从第 {start_index} 校继续（上次: {ckpt.get('current_school', '?')}）")

            # 选择目标学校
            if layers:
                target_schools = select_schools_by_layers(db, layers, limit=args.top_n)
            else:
                # 默认：985 + 头部 211
                target_schools = db.query(School).filter(
                    (School.is_985 == 1) | (School.level == "211")
                ).limit(args.top_n).all()

            # 断点续传：跳过已完成的学校
            if start_index > 0:
                target_schools = target_schools[start_index:]

            print(f"  目标学校: {len(target_schools)} 所（跳过前 {start_index} 所）")
            print(f"  省份: {provinces or '默认 10 省'}")
            print(f"  年份: {args.years}")

            score_stats = import_scores_to_db(
                db, School, AdmissionScore,
                schools=target_schools,
                provinces=provinces,
                years=args.years,
                checkpoint_path=args.checkpoint,
                start_school_index=start_index,
            )

            # 全量导入完成后清除断点
            if not layers or set(layers) == {1, 2, 3, 4}:
                clear_checkpoint(args.checkpoint)

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
