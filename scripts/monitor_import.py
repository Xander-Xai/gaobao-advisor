#!/usr/bin/env python3
"""
导入监控脚本 — 实时显示导入进度
用法: python scripts/monitor_import.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from db.database import get_session, init_db
from db.models import AdmissionScore, School


def format_time(seconds):
    """格式化时间"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds / 60)}分钟"
    else:
        return f"{seconds / 3600:.1f}小时"


def monitor():
    init_db()
    db = get_session()

    # 读取 checkpoint
    checkpoint_path = "data/import_checkpoint.json"
    checkpoint = None
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path) as f:
                checkpoint = json.load(f)
        except:
            pass

    # 数据库统计
    total_scores = db.query(AdmissionScore).count()
    schools_with = db.query(AdmissionScore.school_id).distinct().count()
    total_schools = db.query(School).count()

    # 年份分布
    year_stats = (
        db.query(AdmissionScore.year, func.count(AdmissionScore.id))
        .group_by(AdmissionScore.year)
        .order_by(AdmissionScore.year.desc())
        .all()
    )

    # 省份覆盖
    prov_count = db.query(AdmissionScore.province).distinct().count()

    # 打印报告
    print("=" * 60)
    print("  📊 高考数据导入监控报告")
    print("=" * 60)

    if checkpoint:
        idx = checkpoint.get("school_index", 0)
        total = checkpoint.get("total_schools", 3000)
        pct = idx * 100 // total if total else 0

        print(f"\n🎯 导入进度: {idx}/{total} ({pct}%)")
        print(f"🏫 当前学校: {checkpoint.get('current_school', '?')}")

        stats = checkpoint.get("stats", {})
        print("\n📈 本次运行统计:")
        print(f"  新增分数: {stats.get('new_scores', 0):,}")
        print(f"  API 请求: {stats.get('requests', 0):,}")
        print(f"  错误: {stats.get('errors', 0)}")

        # 估算剩余时间
        if idx > 0 and total > 0:
            # 简单估算：假设每校平均时间相同
            # 这里用固定估算，实际可以根据时间戳计算
            print(f"\n⏱️ 预计剩余: ~{format_time((total - idx) * 30)} (约 {(total - idx) * 30 / 3600:.1f}小时)")

    print("\n💾 数据库统计:")
    print(f"  录取分数: {total_scores:,} 条")
    print(f"  有数据院校: {schools_with}/{total_schools} ({schools_with * 100 // total_schools}%)")
    print(f"  省份覆盖: {prov_count}/30")

    print("\n📅 年份分布:")
    for year, count in year_stats:
        print(f"  {year}年: {count:,} 条")

    # 最近修改时间
    if checkpoint:
        last_run = checkpoint.get("last_run", "?")
        print(f"\n🕐 最后更新: {last_run}")

    print("\n" + "=" * 60)

    db.close()


if __name__ == "__main__":
    monitor()
