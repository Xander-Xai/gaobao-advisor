#!/usr/bin/env python3
"""
金句库建设 — 从对话记录中提取高质量回复片段。

策略：
1. 从 conversation_messages 中提取 assistant 回复（长回复优先）
2. 按会话分组，提取关键推荐/分析类回复
3. 自动评分：回复越长、含数据越多，基础分越高
4. 写入 highlights 表

用法:
  python scripts/build_highlights.py [--min-len 50]
"""

import argparse
import os
import re
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session  # noqa: E402
from db.models import Conversation, ConversationMessage, Highlight  # noqa: E402


def score_content(content: str) -> int:
    """给回复内容评分（0-100）"""
    score = 50  # 基础分

    # 长度加成
    length = len(content)
    if length > 1000:
        score += 15
    elif length > 500:
        score += 10
    elif length > 200:
        score += 5

    # 含具体数据加成
    if re.search(r"\d{3}-\d{3}分|\d{4}位|位次\d+|排名\d+|就业率\d+%|平均月薪", content):
        score += 10
    if re.search(r"(985|211|双一流|一本|二本)", content):
        score += 5
    if re.search(r"推荐|建议|优先|首选|关键|注意|千万不要", content):
        score += 5
    if re.search(r"[A-Z+]{2,}", content):
        score += 3  # 含学科等级 A+ 等

    # 短回复降分
    if length < 60:
        score -= 20
    if length < 30:
        score -= 30

    return max(0, min(100, score))


def extract_highlights(min_len: int = 50) -> int:
    """从对话消息中提取金句"""
    db = get_session()
    new_count = 0
    skip_count = 0

    # 检查已有金句
    existing_contents = set()
    for h in db.query(Highlight).all():
        existing_contents.add(h.content[:100])

    # 按会话分组，获取所有有消息的会话
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()

    print(f"共 {len(conversations)} 个会话")

    for conv in conversations:
        # 获取该会话的所有 assistant 回复
        messages = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.conversation_id == conv.id,
                ConversationMessage.role == "assistant",
            )
            .order_by(ConversationMessage.id)
            .all()
        )

        for msg in messages:
            content = msg.content.strip()
            if len(content) < min_len:
                continue

            # 去重
            if content[:100] in existing_contents:
                skip_count += 1
                continue

            score = score_content(content)
            if score < 30:
                skip_count += 1
                continue

            hl = Highlight(
                session_id=conv.session_id or str(conv.id),
                content=content,
                score=score,
                created_at=msg.created_at or datetime.utcnow(),
            )
            db.add(hl)
            new_count += 1
            existing_contents.add(content[:100])

            # 每会话最多 3 条
            if new_count % 3 == 0:
                db.commit()

    db.commit()
    total = db.query(Highlight).count()
    db.close()

    print("\n[完成]")
    print(f"  新增: {new_count} 条金句")
    print(f"  跳过: {skip_count} 条")
    print(f"  数据库总计: {total} 条")
    return new_count


def main():
    parser = argparse.ArgumentParser(description="金句库建设")
    parser.add_argument("--min-len", type=int, default=50, help="最小回复长度")
    args = parser.parse_args()

    print("=" * 60)
    print("  金句库建设")
    print("=" * 60)
    print(f"  最小长度: {args.min_len} 字符")

    extract_highlights(min_len=args.min_len)

    # 输出一些示例
    db = get_session()
    top = db.query(Highlight).order_by(Highlight.score.desc()).limit(5).all()
    if top:
        print("\n[Top 5 金句]:")
        for i, h in enumerate(top, 1):
            print(f"  {i}. [得分{h.score}] {h.content[:80]}...")
    db.close()


if __name__ == "__main__":
    main()
