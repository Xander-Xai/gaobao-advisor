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

    # 读取 checkpoint（支持多个进程）
    checkpoint_paths = [
        ("data/import_checkpoint.json", "2022-2024年"),
        ("data/import_checkpoint_2025.json", "2025年"),
    ]
    checkpoints = []
    for ckpt_path, label in checkpoint_paths:
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path) as f:
                    ckpt = json.load(f)
                    ckpt["_label"] = label
                    checkpoints.append(ckpt)
            except Exception:
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

    if checkpoints:
        for ckpt in checkpoints:
            idx = ckpt.get("school_index", 0)
            total = ckpt.get("total_schools", 3000)
            pct = idx * 100 // total if total else 0
            label = ckpt.get("_label", "")

            print(f"\n🎯 [{label}] {idx}/{total} ({pct}%)")
            print(f"🏫 当前学校: {ckpt.get('current_school', '?')}")

            stats = ckpt.get("stats", {})
            print(f"  新增分数: {stats.get('new_scores', 0):,}")
            print(f"  API 请求: {stats.get('requests', 0):,}")
            print(f"  错误: {stats.get('errors', 0)}")

            # 估算剩余时间
            if idx > 0 and total > 0:
                est_hours = (total - idx) * 30 / 3600
                print(f"⏱️ 预计剩余: ~{format_time((total - idx) * 30)} (约 {est_hours:.1f}小时)")

    print("\n💾 数据库统计:")
    print(f"  录取分数: {total_scores:,} 条")
    print(f"  有数据院校: {schools_with}/{total_schools} ({schools_with * 100 // total_schools}%)")
    print(f"  省份覆盖: {prov_count}/30")

    print("\n📅 年份分布:")
    for year, count in year_stats:
        print(f"  {year}年: {count:,} 条")

    # 最近修改时间
    if checkpoints:
        last_ckpt = max(checkpoints, key=lambda c: c.get("last_run", ""))
        last_run = last_ckpt.get("last_run", "?")
        print(f"\n🕐 最后更新: {last_run}")

    print("\n" + "=" * 60)

    db.close()


if __name__ == "__main__":
    monitor()
