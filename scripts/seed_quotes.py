#!/usr/bin/env python3
"""
行业专家结构化语录库 — 105 条经典语录
来源: dongsheng123132/gaokao-mentor-wisdom 项目
等级: T3（语录内容，归属基本准确）

语录库结构: 6 个分类文件，105 条语录
- zhuanye.json        专业选择（28 条）
- jiuye.json          就业前景（18 条）
- rensheng.json       人生哲理（18 条）
- yuanxiao.json       院校推荐（16 条）
- xuexi.json          学习建议（12 条）
- zhiyuan-celue.json  志愿策略（13 条）

用法:
  python scripts/seed_quotes.py
"""
import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

QUOTES_DIR = os.path.join(PROJECT_ROOT, "knowledge", "quotes")

# 6 个分类文件
CATEGORY_FILES = [
    ("zhuanye", "专业选择", 28),
    ("jiuye", "就业前景", 18),
    ("rensheng", "人生哲理", 18),
    ("yuanxiao", "院校推荐", 16),
    ("xuexi", "学习建议", 12),
    ("zhiyuan-celue", "志愿策略", 13),
]


def main():
    print("=" * 60)
    print("  行业语录库导入与验证")
    print("=" * 60)

    total = 0
    all_quotes = []

    for cat_id, cat_name, expected_count in CATEGORY_FILES:
        path = os.path.join(QUOTES_DIR, f"{cat_id}.json")
        if not os.path.exists(path):
            print(f"  [SKIP] {cat_id}.json 不存在")
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        quotes = data.get("quotes", [])
        all_quotes.extend(quotes)
        total += len(quotes)

        print(f"  [{cat_id}] {cat_name}: {len(quotes)} 条 (期望 {expected_count})")

        # 检查每条语录的完整性
        for q in quotes:
            assert "text" in q, f"  [ERROR] {q.get('id')} 缺少 text 字段"
            assert "tags" in q, f"  [ERROR] {q.get('id')} 缺少 tags 字段"

    print(f"\n[总计] {total} 条语录")
    print(f"  覆盖 6 个分类: {', '.join([c[1] for c in CATEGORY_FILES])}")

    # 按 sentiment 统计
    sentiments = {}
    for q in all_quotes:
        s = q.get("sentiment", "unknown")
        sentiments[s] = sentiments.get(s, 0) + 1
    print(f"  情感分布: {sentiments}")

    # 按 confidence 统计
    confidences = {}
    for q in all_quotes:
        c = q.get("confidence", "unknown")
        confidences[c] = confidences.get(c, 0) + 1
    print(f"  可信度分布: {confidences}")

    # 输出样例
    print(f"\n[样例] 随机展示 3 条语录:")
    import random
    random.seed(42)
    for q in random.sample(all_quotes, min(3, len(all_quotes))):
        print(f"  · [{q.get('category', '?')}] {q['text']}")
        print(f"    标签: {q.get('tags', [])}")
        print(f"    情感: {q.get('sentiment', '?')}")

    # 创建索引文件（用于快速加载）
    index_path = os.path.join(QUOTES_DIR, "_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0.0",
            "total": total,
            "categories": {cat_id: {"name": cat_name, "count": expected_count}
                          for cat_id, cat_name, expected_count in CATEGORY_FILES},
            "all_quotes": all_quotes,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[索引] 已生成 {index_path} ({os.path.getsize(index_path)} bytes)")

    # 关联专业映射（用于按专业查语录）
    major_index = {}
    for q in all_quotes:
        for m in q.get("related_majors", []):
            major_index.setdefault(m, []).append({
                "id": q.get("id"),
                "text": q.get("text"),
                "tags": q.get("tags", []),
                "sentiment": q.get("sentiment"),
            })

    major_index_path = os.path.join(QUOTES_DIR, "_by_major.json")
    with open(major_index_path, "w", encoding="utf-8") as f:
        json.dump(major_index, f, ensure_ascii=False, indent=2)
    print(f"[专业索引] 已生成 {major_index_path} ({len(major_index)} 个专业)")


if __name__ == "__main__":
    main()
