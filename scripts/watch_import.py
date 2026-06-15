#!/usr/bin/env python3
"""
实时监控导入进度
用法: python scripts/watch_import.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def watch():
    checkpoint_path = "data/import_checkpoint.json"
    last_idx = 0
    last_time = time.time()

    print("=" * 60)
    print("  📊 高考数据导入实时监控")
    print("=" * 60)
    print("  按 Ctrl+C 退出")
    print("=" * 60)

    try:
        while True:
            if os.path.exists(checkpoint_path):
                try:
                    with open(checkpoint_path) as f:
                        cp = json.load(f)

                    idx = cp.get("school_index", 0)
                    total = cp.get("total_schools", 3000)
                    pct = idx * 100 // total
                    stats = cp.get("stats", {})
                    current = cp.get("current_school", "?")

                    # 计算速度
                    now = time.time()
                    if idx > last_idx:
                        speed = (idx - last_idx) / (now - last_time) * 60  # 校/分钟
                        eta = (total - idx) / speed if speed > 0 else 0
                        last_idx = idx
                        last_time = now
                    else:
                        speed = 0
                        eta = 0

                    # 清屏（可选）
                    # os.system('clear')

                    print(
                        f"\r🎯 {idx}/{total} ({pct}%) | 🏫 {current} | 📈 +{stats.get('new_scores', 0):,} | "
                        f"🌐 {stats.get('requests', 0):,} | ❌ {stats.get('errors', 0)} | "
                        f"⚡ {speed:.1f}校/分 | ⏱️  ETA: {eta / 60:.1f}h",
                        end="",
                        flush=True,
                    )

                except Exception as e:
                    print(f"\r[读取失败: {e}]", end="", flush=True)

            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n监控已退出")


if __name__ == "__main__":
    watch()
