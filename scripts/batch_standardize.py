#!/usr/bin/env python3
"""
批次名称标准化 — 将50+种批次名映射为6个标准批次

标准批次:
- 本科提前批
- 本科一批
- 本科二批
- 本科批 (新高考合并批次省份)
- 专科批
- 其他 (专项计划、预科等)

用法:
  python scripts/batch_standardize.py --dry-run
  python scripts/batch_standardize.py
"""

import argparse
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db
from db.models import AdmissionScore
from sqlalchemy import func, text

# 标准化映射规则（按优先级匹配，更具体的规则放前面）
BATCH_RULES = [
    # 专科提前批（必须在"提前批"规则之前，否则会被误匹配）
    (re.compile(r"专科提前批|高职专科提前批"), "专科批"),
    # 本科提前批
    (re.compile(r"本科提前批|提前批[AB]?[段类]?|普通类提前批|提前本科批|提前[一二]批本科|本科提前二批"), "本科提前批"),
    # 本科一批
    (re.compile(r"本科一批|本科批A段|普通类一段(?!二)|本科一段"), "本科一批"),
    # 本科二批
    (re.compile(r"本科二批|本科批B段|本科二批及预科|普通类二段|本科二段|平行录取二段"), "本科二批"),
    # 本科批（新高考合并批次）
    (re.compile(r"^本科批$|平行录取一段|平行录取|普通类平行录取"), "本科批"),
    # 专科批
    (re.compile(r"专科|高职|普通类三段"), "专科批"),
    # 本科批C段
    (re.compile(r"本科批C段"), "本科批"),
    # 特殊类型
    (re.compile(r"专项|预科|特殊类型|综合评价|国家专项|地方专项|高校专项|高校农村"), "其他"),
    # 艺术体育
    (re.compile(r"艺术|体育|民航|飞行"), "其他"),
    # 零志愿等
    (re.compile(r"零志愿|高本贯通"), "其他"),
]

# 无法自动映射的批次 → 手动映射
MANUAL_MAPPINGS = {
    "国家及地方专项、南疆单列、对口援疆计划本科二批次": "其他",
    "国家及地方专项、南疆单列、对口援疆计划本科一批次": "其他",
    "本科批（特殊类型）": "其他",
    "本科批（区域教育均衡发展专项）": "其他",
    "本科批（预科）": "其他",
    "本科批A段（地方专项）": "其他",
    "本科批A段（国家专项）": "其他",
    "本科批（原少数民族语言授课为主）": "其他",
    "本科批（原加授少数民族语文）": "其他",
    "国家专项计划本科批": "其他",
    "国家专项计划批": "其他",
    "地方专项计划批": "其他",
    "高校专项计划批": "其他",
    "地方农村专项计划": "其他",
    "地方农村专项计划批次": "其他",
    "高校农村专项计划": "其他",
    "本科预科班批": "其他",
    "综合评价批次": "其他",
    "高本贯通批": "其他",
    # 新增手动映射（正则难以准确匹配的特殊批次）
    "提前一批本科": "本科提前批",
    "提前二批本科": "本科提前批",
    "提前本科批": "本科提前批",
    "本科提前二批": "本科提前批",
    "免费定向批（本科）": "其他",
    "一本预科": "其他",
    "国家及地方专项、南疆单列、对口援疆计划本科二批": "其他",
    "国家及地方专项、南疆单列、对口援疆计划本科一批": "其他",
    "国家专项计划(本二)": "其他",
    "本科批（高校专项）": "其他",
    "本科批（民委专项）": "其他",
    "本科提前批（高校专项）": "本科提前批",
    "本科提前批（国家专项）": "本科提前批",
}


def standardize_batch(batch_name: str) -> str | None:
    """将原始批次名映射为标准批次名"""
    if not batch_name:
        return None

    # 先查手动映射
    if batch_name in MANUAL_MAPPINGS:
        return MANUAL_MAPPINGS[batch_name]

    # 再用正则匹配
    for pattern, std_batch in BATCH_RULES:
        if pattern.search(batch_name):
            return std_batch

    return "其他"  # 兜底


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    db = get_session()

    try:
        # 获取所有不同的批次名
        batch_names = db.query(AdmissionScore.batch, func.count(AdmissionScore.id)).group_by(
            AdmissionScore.batch
        ).order_by(func.count(AdmissionScore.id).desc()).all()

        print(f"共 {len(batch_names)} 种批次名称\n")

        # 显示映射结果
        unmapped = []
        for batch, count in batch_names:
            std = standardize_batch(batch)
            if std is None:
                unmapped.append((batch, count))
            flag = "" if std else " ⚠️ 未映射"
            print(f"  {batch} ({count:,}) → {std}{flag}")

        if unmapped:
            print(f"\n⚠️ {len(unmapped)} 种批次未映射:")
            for b, c in unmapped:
                print(f"  {b} ({c:,})")

        if args.dry_run:
            print("\n[dry-run] 不更新数据库")
            return

        # 更新数据库
        updated = 0
        for batch, count in batch_names:
            std = standardize_batch(batch)
            if std:
                affected = db.query(AdmissionScore).filter(
                    AdmissionScore.batch == batch,
                    AdmissionScore.standardized_batch.is_(None)
                ).update({"standardized_batch": std})
                updated += affected

        db.commit()
        print(f"\n更新 {updated} 条记录的 standardized_batch")

        # 验证覆盖率
        total = db.query(AdmissionScore).count()
        with_std = db.query(AdmissionScore).filter(
            AdmissionScore.standardized_batch.isnot(None)
        ).count()
        print(f"标准化覆盖率: {with_std}/{total} ({with_std/total*100:.1f}%)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
