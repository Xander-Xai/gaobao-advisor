"""
model_selector — 模型选择矩阵（思维框架调度器）

根据用户场景自动推荐首选/辅助/禁用的心智模型，
并检测是否触发强制降级条件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── 5 大心智模型 ────────────────────────────────────────────

MODELS = {
    "sieve":        "社会筛子论",
    "choice_effort": "选择>努力",
    "job_reverse":  "就业倒推法",
    "class_real":   "阶层现实主义",
    "controversy":  "争议即传播",
}


# ── 场景 → 模型矩阵 ────────────────────────────────────────

@dataclass
class ModelConfig:
    """场景对应的模型配置。"""
    preferred: list[str]   # 首选模型
    auxiliary: list[str]    # 辅助模型
    banned: list[str]       # 禁用模型


SCENARIO_MODELS: dict[str, ModelConfig] = {
    "普通家庭高考填志愿": ModelConfig(
        preferred=["job_reverse", "class_real"],
        auxiliary=["sieve", "city_priority"],
        banned=[],
    ),
    "富裕家庭高考填志愿": ModelConfig(
        preferred=["job_reverse"],
        auxiliary=["choice_effort"],
        banned=["class_real"],
    ),
    "有强烈学术志向": ModelConfig(
        preferred=["choice_effort"],
        auxiliary=["job_reverse"],
        banned=["class_real"],
    ),
    "考研/读博决策": ModelConfig(
        preferred=["job_reverse", "sieve"],
        auxiliary=["choice_effort"],
        banned=[],
    ),
    "复读决策": ModelConfig(
        preferred=["choice_effort"],
        auxiliary=["job_reverse"],
        banned=[],
    ),
    "情绪崩溃/高考失利": ModelConfig(
        preferred=["choice_effort"],  # 温和版：方向比努力更重要
        auxiliary=["job_reverse"],
        banned=["controversy"],       # 不用极端表达
    ),
    "纯教育理念讨论": ModelConfig(
        preferred=["sieve"],
        auxiliary=[],
        banned=[],
    ),
    "职业转型/跳槽": ModelConfig(
        preferred=["choice_effort", "job_reverse"],
        auxiliary=[],
        banned=[],
    ),
}

# 对话阶段 → 模型适配
PHASE_MODELS: dict[str, ModelConfig] = {
    "探测期": ModelConfig(
        preferred=["choice_effort"],
        auxiliary=[],
        banned=[],
    ),
    "定向期": ModelConfig(
        preferred=["job_reverse"],
        auxiliary=[],
        banned=[],
    ),
    "精准推荐期": ModelConfig(
        preferred=["class_real", "job_reverse"],
        auxiliary=[],
        banned=[],
    ),
    "风险审查期": ModelConfig(
        preferred=["job_reverse", "sieve"],
        auxiliary=[],
        banned=[],
    ),
}


# ── 降级触发器 ──────────────────────────────────────────────

@dataclass
class DowngradeTrigger:
    """降级触发信号。"""
    id: int
    signal: str
    action: str
    switch_to: list[str]
    disable: list[str]


_DOWNGRADE_TRIGGERS: list[DowngradeTrigger] = [
    DowngradeTrigger(
        id=1,
        signal="用户明确表达非就业导向（学术/公益/艺术）",
        action="暂停阶层现实主义和就业倒推法，改用选择>努力，但仍做风险提示",
        switch_to=["choice_effort"],
        disable=["class_real", "job_reverse"],
    ),
    DowngradeTrigger(
        id=2,
        signal="数据显示用户判断可能正确（冷门专业但就业不错）",
        action="跳出预设立场，用数据说话",
        switch_to=["job_reverse"],  # 用就业倒推法看数据，不用阶层现实主义预判
        disable=[],
    ),
    DowngradeTrigger(
        id=3,
        signal="用户分数在极端边界（差 1-3 分）",
        action="暂停确定性判断，改为概率分析",
        switch_to=[],
        disable=[],
    ),
    DowngradeTrigger(
        id=4,
        signal="用户情绪明显低落",
        action="立即执行情绪危机 SOP，切换到共情优先档",
        switch_to=["choice_effort"],
        disable=["controversy"],
    ),
]


# ── 场景推断 ─────────────────────────────────────────────────

def infer_scenario(slots: dict[str, Any], user_input: str = "") -> str:
    """根据用户槽位和输入推断场景。

    Args:
        slots: 已采集的槽位信息。
        user_input: 用户最新输入文本。

    Returns:
        场景字符串，用于从 SCENARIO_MODELS 查找模型配置。
    """
    goal = (slots.get("goal") or "").strip()
    family = (slots.get("family") or "").strip()
    interest = (slots.get("interest") or "").strip()

    combined = f"{goal} {interest} {user_input}"

    # 情绪信号优先检测
    emotion_words = ["崩溃", "没希望", "想死", "完蛋", "不想活", "绝望",
                     "考砸了", "考差了", "心态崩了", "废了"]
    if any(w in user_input for w in emotion_words):
        return "情绪崩溃/高考失利"

    # 复读决策
    if "复读" in combined:
        return "复读决策"

    # 考研/读博
    if "考研" in combined or "读博" in combined or "深造" in combined:
        return "考研/读博决策"

    # 家庭背景分流
    if family:
        rich_words = ["做生意", "有矿", "富裕", "有钱", "能负担", "私立", "中外合作"]
        if any(w in family for w in rich_words):
            return "富裕家庭高考填志愿"
        # 学术志向
        if "学术" in combined or "科研" in combined:
            return "有强烈学术志向"
        return "普通家庭高考填志愿"

    # 职业转型
    if "跳槽" in combined or "转行" in combined:
        return "职业转型/跳槽"

    # 默认普通家庭
    return "普通家庭高考填志愿"


def infer_phase(slots: dict[str, Any], conversation_round: int = 1) -> str:
    """根据槽位完整度和对话轮次推断当前阶段。

    Returns:
        "探测期" / "定向期" / "精准推荐期" / "风险审查期"
    """
    score_filled = bool(slots.get("score"))
    province_filled = bool(slots.get("province"))
    goal_filled = bool(slots.get("goal"))
    family_filled = bool(slots.get("family"))

    # 核心槽位齐全 → 精准推荐期
    if score_filled and province_filled and goal_filled:
        return "精准推荐期"

    # 有分数但缺诉求 → 定向期
    if score_filled and province_filled:
        return "定向期"

    # 缺分数 → 探测期
    return "探测期"


# ── 主 API ──────────────────────────────────────────────────

def select_models(
    slots: dict[str, Any],
    user_input: str = "",
    scenario: str | None = None,
    phase: str | None = None,
) -> dict:
    """根据用户场景选择推荐的模型组合。

    Args:
        slots: 已采集的槽位。
        user_input: 用户最新输入。
        scenario: 强制指定场景（可选）。
        phase: 强制指定对话阶段（可选）。

    Returns:
        {
            "scenario": str,
            "phase": str,
            "preferred": [str],   # 首选模型名列表
            "auxiliary": [str],   # 辅助模型名列表
            "banned": [str],      # 禁用模型名列表
            "all_allowed": [str], # preferred + auxiliary
            "downgrade_triggers": [dict],  # 可能触发的降级条件
        }
    """
    if scenario is None:
        scenario = infer_scenario(slots, user_input)
    if phase is None:
        phase = infer_phase(slots)

    config = SCENARIO_MODELS.get(scenario, SCENARIO_MODELS["普通家庭高考填志愿"])
    phase_config = PHASE_MODELS.get(phase)

    preferred = list(config.preferred)
    auxiliary = list(config.auxiliary)
    banned = list(config.banned)

    # 合并阶段推荐
    if phase_config:
        for m in phase_config.preferred:
            if m not in preferred and m not in banned:
                preferred.append(m)

    # 检查降级触发器
    triggered_triggers = []
    for trigger in _DOWNGRADE_TRIGGERS:
        # 简单信号匹配
        if trigger.id == 1 and slots.get("goal") and any(
            w in (slots["goal"] or "") for w in ["学术", "公益", "艺术", "科研"]
        ):
            triggered_triggers.append({
                "id": trigger.id,
                "signal": trigger.signal,
                "action": trigger.action,
            })
        elif trigger.id == 4 and any(
            w in user_input for w in ["崩溃", "没希望", "绝望", "想死", "废了"]
        ):
            triggered_triggers.append({
                "id": trigger.id,
                "signal": trigger.signal,
                "action": trigger.action,
            })

    return {
        "scenario": scenario,
        "phase": phase,
        "preferred": [MODELS.get(m, m) for m in preferred if m in MODELS],
        "auxiliary": [MODELS.get(m, m) for m in auxiliary if m in MODELS],
        "banned": [MODELS.get(m, m) for m in banned if m in MODELS],
        "all_allowed": [MODELS.get(m, m) for m in (preferred + auxiliary) if m in MODELS],
        "downgrade_triggers": triggered_triggers,
    }


def format_model_hint(result: dict) -> str:
    """格式化模型选择结果为可读提示（用于日志/调试）。"""
    parts = [f"场景：{result['scenario']} | 阶段：{result['phase']}"]
    if result["preferred"]:
        parts.append(f"首选：{'、'.join(result['preferred'])}")
    if result["auxiliary"]:
        parts.append(f"辅助：{'、'.join(result['auxiliary'])}")
    if result["banned"]:
        parts.append(f"禁用：{'、'.join(result['banned'])}")
    if result["downgrade_triggers"]:
        parts.append(f"⚠️ 降级触发：{len(result['downgrade_triggers'])} 条")
    return " | ".join(parts)
