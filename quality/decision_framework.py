"""
decision_framework — 8 条决策启发式调用器

基于用户信息（省份/分数/家庭/诉求等）自动推荐适用的启发式组合，
用于在 AI 给建议前做内部校验。
"""

from __future__ import annotations

from typing import Any

# ── 启发式定义 ──────────────────────────────────────────────

HEURISTICS: dict[str, dict[str, str]] = {
    "soul_interrogation": {
        "name": "灵魂追问法",
        "desc": "面对任何选择，连问'分数/省份/家庭/城市/行业'。先追问建立框架，不先上来就给答案。",
        "when": "任何咨询开始时",
    },
    "median_principle": {
        "name": "中位数原则",
        "desc": "评估专业/行业时，看中间 50% 的人过得怎样，不看顶尖案例。",
        "when": "评估专业/行业/院校时",
    },
    "irreplaceability": {
        "name": "不可替代性检验",
        "desc": "你的工资和不可替代性成正比。问'如果明天被替换，老板多久找到替代者？'",
        "when": "评估职业方向/是否跳槽时",
    },
    "fortune500_test": {
        "name": "500 强测试",
        "desc": "别听企业怎么说，看企业怎么做。他们去哪校招？招什么专业？给多少钱？",
        "when": "判断学历/专业的真实市场价值时",
    },
    "family_routing": {
        "name": "家庭背景分流",
        "desc": "第一句话必问家庭条件。有矿没矿，策略完全不同。没问就给建议=耍流氓。",
        "when": "任何给建议的场景（必选）",
    },
    "city_priority": {
        "name": "城市优先原则",
        "desc": "优先选发达城市。城市给你的是思维、资源和机会的差距。",
        "when": "院校选择/城市抉择时",
    },
    "ten_year_test": {
        "name": "10 年压迫测试",
        "desc": "你能不能接受孩子工作 10 年后，收入比当年分数不如他的人更低？",
        "when": "帮犹豫的人做最终决策时",
    },
    "apology_method": {
        "name": "认态度不认事实（道歉法）",
        "desc": "核心观点绝不让步，只调整表达方式。涉及措辞不当可以道歉，涉及核心判断死不松口。",
        "when": "面对争议和批评时",
    },
}


# ── 场景 → 启发式映射 ──────────────────────────────────────

SCENARIO_HEURISTICS: dict[str, list[str]] = {
    # 通用咨询（必选）
    "default": ["soul_interrogation", "family_routing"],

    # 专业/行业评估
    "major_evaluation": ["median_principle", "irreplaceability", "fortune500_test"],
    # 院校/城市选择
    "school_selection": ["city_priority", "fortune500_test"],
    # 家庭决策分流
    "family_decision": ["family_routing", "ten_year_test"],
    # 犹豫/纠结
    "hesitation": ["ten_year_test", "irreplaceability"],
    # 复读决策
    "repeat_year": ["ten_year_test", "median_principle", "family_routing"],
    # 考研/深造
    "grad_school": ["median_principle", "irreplaceability", "fortune500_test"],
    # 就业导向
    "employment": ["median_principle", "fortune500_test", "irreplaceability"],
    # 面对争议
    "controversy": ["apology_method"],
}


# ── 槽位 → 场景推断 ─────────────────────────────────────────

def infer_scenario(slots: dict[str, Any]) -> str:
    """根据已采集的槽位推断当前场景。

    Args:
        slots: 包含 province, score, subject, interest, region, family, goal 等字段。

    Returns:
        场景字符串，用于从 SCENARIO_HEURISTICS 查找推荐启发式。
    """
    goal = (slots.get("goal") or "").strip()
    family = (slots.get("family") or "").strip()
    interest = (slots.get("interest") or "").strip()

    # 复读决策
    if "复读" in goal or "复读" in interest:
        return "repeat_year"

    # 考研/深造
    if "考研" in goal or "读研" in goal or "深造" in goal:
        return "grad_school"

    # 就业导向
    if "就业" in goal or "找工作" in goal or "高薪" in goal or "稳定" in goal:
        return "employment"

    # 院校/城市选择
    if slots.get("region") and slots.get("score"):
        return "school_selection"

    # 专业评估
    if interest and interest not in ("不知道", "不清楚", "随便"):
        return "major_evaluation"

    # 家庭特殊背景
    if family and family not in ("普通家庭", "没资源", "条件一般"):
        return "family_decision"

    return "default"


# ── 主 API ──────────────────────────────────────────────────

def recommend_heuristics(slots: dict[str, Any], scenario: str | None = None) -> list[dict]:
    """根据用户槽位推荐适用的决策启发式。

    Args:
        slots: 用户已采集的槽位信息。
        scenario: 强制指定场景（可选），不指定则自动推断。

    Returns:
        推荐的启发式列表，每项包含 name, desc, when。
    """
    if scenario is None:
        scenario = infer_scenario(slots)

    # 默认启发式（必选）
    keys = list(SCENARIO_HEURISTICS["default"])

    # 场景特定启发式
    if scenario in SCENARIO_HEURISTICS:
        for k in SCENARIO_HEURISTICS[scenario]:
            if k not in keys:
                keys.append(k)

    return [{"key": k, **HEURISTICS[k]} for k in keys if k in HEURISTICS]


def get_heuristic(key: str) -> dict | None:
    """按 key 获取单条启发式。"""
    return {"key": key, **HEURISTICS[key]} if key in HEURISTICS else None


def list_heuristics() -> dict[str, dict]:
    """返回全部 8 条启发式定义。"""
    return {k: dict(v) for k, v in HEURISTICS.items()}
