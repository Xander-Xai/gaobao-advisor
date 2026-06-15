"""
上下文知识加载器（v2 — 接入 kb_retriever）。

当 ENABLE_RAG_KB=true 时，委托给 KbRetriever 进行语义检索。
当 ENABLE_RAG_KB=false 时，保留旧的关键词触发逻辑作为 fallback。
"""

from __future__ import annotations

import os
from typing import Any

# ── 旧系统（fallback） ────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)

_KNOWLEDGE_TRIGGERS: dict[str, dict[str, Any]] = {
    "00_ai_era_correction.md": {
        "name": "AI时代校正框架",
        "triggers": [
            "AI",
            "人工智能",
            "机器人",
            "自动化",
            "AI时代",
            "就业冲击",
            "被替代",
            "计算机",
            "软件",
            "编程",
            "算法",
            "数据科学",
            "深度学习",
            "大模型",
            "chatgpt",
            "gpt",
            "deepseek",
            "芯片",
            "半导体",
        ],
        "priority": 1,
    },
    "06_university_life_planning.md": {
        "name": "大学在校4年规划",
        "triggers": [
            "大学怎么过",
            "大学规划",
            "大一",
            "大二",
            "大三",
            "大四",
            "四年",
            "在校",
            "大学生活",
            "要不要考研",
            "考研规划",
            "实习",
            "竞赛",
            "社团",
            "保研",
        ],
        "priority": 2,
    },
    "07_new_gaokao_subject_selection.md": {
        "name": "新高考选科指南",
        "triggers": [
            "选科",
            "选考",
            "3+1+2",
            "3+3",
            "物理",
            "历史",
            "化学",
            "生物",
            "政治",
            "地理",
            "技术",
            "赋分",
            "等级赋分",
            "新高考",
            "选科组合",
            "学科组合",
        ],
        "priority": 1,
    },
    "08_vocational_strategy.md": {
        "name": "职业教育策略",
        "triggers": ["专科", "高职", "大专", "职业技术", "技能", "专升本", "三校生", "中专", "技校", "职业本科"],
        "priority": 2,
    },
}

_KNOWLEDGE_DIR = os.path.join(_PROJECT_ROOT, "knowledge")

# ── 文件缓存 ──────────────────────────────────────────────────
_FILE_CACHE: dict[str, str] = {}


def _load_file(filename: str) -> str:
    """读取 knowledge/ 目录下的文件（带缓存）。"""
    if filename in _FILE_CACHE:
        return _FILE_CACHE[filename]
    path = os.path.join(_KNOWLEDGE_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    _FILE_CACHE[filename] = content
    return content


# ── 新系统接口 ────────────────────────────────────────────────
def load_contextual_knowledge(
    user_msg: str,
    slots: dict | None = None,
    max_files: int = 2,
    kb_retriever=None,
) -> str | None:
    """根据用户问题和槽位，按需加载相关知识内容。

    Args:
        user_msg: 用户最新输入文本。
        slots: 已采集的槽位信息（可选）。
        max_files: 最多加载几个文件（默认 2，节省 token）。
        kb_retriever: KbRetriever 实例（新系统传入）。

    Returns:
        拼接后的知识内容，或 None（无匹配时）。
    """
    # ── 新系统：委托给 KbRetriever ──
    if kb_retriever is not None:
        try:
            result = kb_retriever.search(user_msg, slots or {})
            if result.group_chunks:
                return "\n\n".join(c.text for c in result.group_chunks[: max_files * 3])
        except Exception:
            pass  # 降级到旧系统

    # ── 旧系统：关键词触发 ──
    combined_text = user_msg.lower()
    if slots:
        for slot_val in slots.values():
            if isinstance(slot_val, dict) and "value" in slot_val:
                combined_text += " " + str(slot_val["value"]).lower()

    scored: list[tuple[str, float, int]] = []
    for filename, meta in _KNOWLEDGE_TRIGGERS.items():
        hits = sum(1 for t in meta["triggers"] if t.lower() in combined_text)
        if hits > 0:
            scored.append((filename, float(hits), meta["priority"]))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[1], x[2]))
    selected = scored[:max_files]

    parts: list[str] = []
    for filename, _, _ in selected:
        content = _load_file(filename)
        if content:
            parts.append(content)

    return "\n\n".join(parts) if parts else None
