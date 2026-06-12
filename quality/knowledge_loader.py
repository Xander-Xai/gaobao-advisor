"""
knowledge_loader — 知识库按需加载器

根据用户问题关键词，动态加载 knowledge/ 目录下的相关知识文件，
避免全量加载（节省 token）。
"""

from __future__ import annotations
import os
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_DIR = os.path.join(os.path.dirname(_HERE), "knowledge")

# ── 知识文件 → 触发关键词映射 ────────────────────────────────

_KNOWLEDGE_TRIGGERS: dict[str, dict[str, Any]] = {
    "00_ai_era_correction.md": {
        "name": "AI时代校正框架",
        "triggers": ["AI", "人工智能", "机器人", "自动化", "AI时代", "就业冲击", "被替代",
                      "计算机", "软件", "编程", "算法", "数据科学", "深度学习",
                      "大模型", "chatgpt", "gpt", "deepseek", "芯片", "半导体"],
        "priority": 1,
    },
    "06_university_life_planning.md": {
        "name": "大学在校4年规划",
        "triggers": ["大学怎么过", "大学规划", "大一", "大二", "大三", "大四",
                      "四年", "在校", "大学生活", "要不要考研", "考研规划",
                      "实习", "竞赛", "社团", "保研"],
        "priority": 2,
    },
    "07_new_gaokao_subject_selection.md": {
        "name": "新高考选科指南",
        "triggers": ["选科", "选考", "3+1+2", "3+3", "物理", "历史",
                      "化学", "生物", "政治", "地理", "技术", "赋分",
                      "等级赋分", "新高考", "选科组合", "学科组合"],
        "priority": 1,
    },
    "08_vocational_strategy.md": {
        "name": "职业教育策略",
        "triggers": ["专科", "高职", "大专", "职业技术", "技能",
                      "专升本", "三校生", "中专", "技校", "职业本科"],
        "priority": 2,
    },
}

# 缓存已加载的知识文件
_cache: dict[str, str] = {}


def _load_file(filename: str) -> str | None:
    """从 knowledge/ 目录加载文件，带缓存。"""
    if filename in _cache:
        return _cache[filename]
    filepath = os.path.join(_KNOWLEDGE_DIR, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        _cache[filename] = content
        return content
    except Exception:
        return None


def load_contextual_knowledge(user_msg: str, slots: dict | None = None, max_files: int = 2) -> str | None:
    """根据用户问题和槽位，按需加载相关知识文件。

    Args:
        user_msg: 用户最新输入文本。
        slots: 已采集的槽位信息（可选）。
        max_files: 最多加载几个文件（默认 2，节省 token）。

    Returns:
        拼接后的知识内容，或 None（无匹配时）。
    """
    combined_text = user_msg.lower()
    if slots:
        for slot_val in slots.values():
            if isinstance(slot_val, dict) and slot_val.get("value"):
                combined_text += " " + str(slot_val["value"]).lower()
            elif isinstance(slot_val, str):
                combined_text += " " + slot_val.lower()

    # 计算每个文件的匹配得分
    scores: list[tuple[str, int, int]] = []  # (filename, score, priority)
    for filename, config in _KNOWLEDGE_TRIGGERS.items():
        score = 0
        for trigger in config["triggers"]:
            if trigger.lower() in combined_text:
                score += 1
        if score > 0:
            scores.append((filename, score, config["priority"]))

    if not scores:
        return None

    # 按得分降序，得分相同按优先级升序
    scores.sort(key=lambda x: (-x[1], x[2]))

    # 加载前 max_files 个
    loaded_parts: list[str] = []
    for filename, score, _ in scores[:max_files]:
        content = _load_file(filename)
        if content:
            config = _KNOWLEDGE_TRIGGERS[filename]
            loaded_parts.append(f"【{config['name']}】\n{content}")

    return "\n\n".join(loaded_parts) if loaded_parts else None


def clear_cache():
    """清空知识文件缓存。"""
    _cache.clear()
