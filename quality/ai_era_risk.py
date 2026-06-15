"""
AI时代专业风险评估模块 — 结构化风险数据查询。
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "ai_era_risk_data.json")
_risk_data = None


def _load_data() -> dict:
    global _risk_data
    if _risk_data is None:
        if os.path.exists(_DATA_PATH):
            with open(_DATA_PATH, encoding="utf-8") as f:
                _risk_data = json.load(f)
        else:
            _risk_data = {}
    return _risk_data


def get_major_risk(major_name: str) -> dict | None:
    """查询专业的AI风险评估。精确匹配优先，模糊匹配兜底。"""
    if not major_name or not isinstance(major_name, str):
        return None
    data = _load_data()
    if major_name in data:
        return data[major_name]
    for key in data:
        if major_name in key or key in major_name:
            return data[key]
    return None


def get_risk_summary(major_name: str) -> str | None:
    """获取专业风险的一句话摘要（用于注入LLM提示）。"""
    risk = get_major_risk(major_name)
    if not risk:
        return None
    return f"{risk['risk_zone']} {major_name}：{risk['ai_impact']}。建议：{risk['recommendation']}"
