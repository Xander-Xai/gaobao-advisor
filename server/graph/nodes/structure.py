"""Structure output node — builds a StructuredPlanningCard from gathered data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from config.loader import load_tuning
from server.domain.schemas import StructuredPlanningCard

# Thresholds loaded from tuning.yaml
_DEFAULT_SLOT_COUNT = 7
# Slot keys required for next actions
MISSING_SLOT_KEYS = ["province", "score_rank", "subject", "interest", "goal"]


def _get_thresholds() -> dict:
    """Load dynamic thresholds from tuning.yaml."""
    return load_tuning().get("thresholds", {})


def _slot_value(slots: dict, *keys: str) -> Any:
    """Read a slot value from flat or nested slot representations."""
    for key in keys:
        val = slots.get(key)
        if isinstance(val, dict):
            val = val.get("value", "")
        if val:
            return val
    return ""


def _score_value(slots: dict) -> Any:
    return _slot_value(slots, "score_rank", "score")


_TITLE_MAP = {
    "gaokao": "高考志愿规划建议",
    "kaoyan": "考研规划建议",
    "career": "职业发展建议",
    "general": "教育规划建议",
}


def structure_output_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build a StructuredPlanningCard from reasoning and data query results.

    Extracts facts, suggestions, risks, and next_actions from the state,
    producing a structured JSON payload for the frontend.
    Falls back to a minimal card if extraction fails.
    """
    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    data = state.get("data_query_results", {})
    reasoning = state.get("reasoning", "")

    try:
        facts = _extract_facts(slots, data, reasoning)
        suggestions = _extract_suggestions(scene, data, reasoning)
        risks = _extract_risks(scene, data, slots)
        next_actions = _extract_next_actions(scene, slots, data)
        summary = _build_summary(scene, slots, data)

        filled_count = len([v for v in slots.values() if v])
        total_slots = max(len(slots) if slots else _DEFAULT_SLOT_COUNT, 1)
        confidence = round(filled_count / total_slots, 2)
        match_schools = data.get("match_schools", [])
        if match_schools:
            confidence = min(confidence, min(_provenance_confidence_cap(item) for item in match_schools))

        card = StructuredPlanningCard(
            title=_TITLE_MAP.get(scene, "教育规划建议"),
            summary=summary,
            scene=scene,
            facts=facts,
            suggestions=suggestions,
            risks=risks,
            next_actions=next_actions,
            confidence=confidence,
        )
        structured = card.model_dump()
    except Exception:
        # Graceful fallback: minimal card
        structured = StructuredPlanningCard(
            title=_TITLE_MAP.get(scene, "教育规划建议"),
            summary="数据不足，建议补充更多信息。",
            scene=scene,
        ).model_dump()

    trace = list(state.get("trace", []))
    trace.append({"node": "structure_output", "event": "card_built"})
    return {"structured_result": structured, "trace": trace}


def _extract_facts(slots: dict, data: dict, reasoning: str) -> list[str]:
    """Extract factual statements from slots, data, and reasoning."""
    facts: list[str] = []

    slot_labels = {
        "province": "省份",
        "score_rank": "分数",
        "subject": "选科",
        "interest": "专业意向",
        "region": "地域偏好",
        "family": "家庭背景",
        "goal": "核心诉求",
    }
    for key, label in slot_labels.items():
        val = _score_value(slots) if key == "score_rank" else _slot_value(slots, key)
        if val:
            facts.append(f"{label}：{val}")

    match_schools = data.get("match_schools", [])
    if match_schools:
        names = [s.get("school_name", s.get("name", "")) for s in match_schools[:5]]
        names = [n for n in names if n]
        if names:
            facts.append(f"匹配院校：{', '.join(names)}")

    rank_info = data.get("rank_info")
    if rank_info:
        facts.append(f"位次分析：{rank_info}")

    major_info = data.get("major_info")
    if major_info and isinstance(major_info, dict):
        name = major_info.get("name", "")
        emp = major_info.get("employment_rate")
        if name:
            emp_str = f"，就业率{emp * 100:.0f}%" if emp else ""
            facts.append(f"专业信息：{name}{emp_str}")

    return facts


def _extract_suggestions(scene: str, data: dict, reasoning: str) -> list[str]:
    """Extract actionable suggestions from data and reasoning."""
    suggestions: list[str] = []

    match_schools = data.get("match_schools", [])
    if match_schools and scene == "gaokao":
        for s in match_schools[:3]:
            name = s.get("school_name", s.get("name", ""))
            score = s.get("min_score", s.get("score_line", ""))
            level = s.get("school_level", "")
            if name:
                tag = f"（{level}）" if level else ""
                score_str = f"，参考线{score}分" if score else ""
                suggestions.append(f"候选：{name}{tag}{score_str}{_provenance_label(s)}")

    if not suggestions:
        suggestions.append("建议补充更多信息以获得精准推荐")

    return suggestions


def _is_synthetic(record: dict[str, Any]) -> bool:
    source_text = " ".join(
        str(record.get(key, "")) for key in ("data_source", "source", "source_label", "data_source_note")
    ).lower()
    return bool(record.get("synthetic")) or "synthetic demo" in source_text or "合成演示" in source_text


def _provenance_label(record: dict[str, Any]) -> str:
    if _is_synthetic(record) or record.get("provenance_status") == "synthetic":
        return "【合成演示数据，不可用于真实志愿决策】"

    year = record.get("year")
    source = record.get("data_source") or record.get("source")
    if not year or not source or "无法验证" in str(source):
        return "【来源或年份无法验证，不作为录取依据；请查省考试院和高校官网】"

    try:
        historical = int(year) < datetime.now().year - 2
    except (TypeError, ValueError):
        historical = True
    age_label = "；历史数据" if historical else ""
    return f"（来源：{source}；数据年份：{year}{age_label}；请以省考试院和高校官网最新信息为准）"


def _provenance_confidence_cap(record: dict[str, Any]) -> float:
    if _is_synthetic(record) or record.get("provenance_status") == "synthetic":
        return 0.0
    year = record.get("year")
    source = record.get("data_source") or record.get("source")
    if not year or not source or "无法验证" in str(source):
        return 0.2
    try:
        if int(year) < datetime.now().year - 2:
            return 0.4
    except (TypeError, ValueError):
        return 0.2
    return 0.8


def _extract_risks(scene: str, data: dict, slots: dict) -> list[str]:
    """Extract risk warnings."""
    risks: list[str] = []

    if scene == "gaokao":
        thresholds = _get_thresholds()
        low_score = thresholds.get("low_score", 450)
        high_risk = set(thresholds.get("high_risk_majors", []))

        score = _score_value(slots)
        if score:
            try:
                score_num = int(str(score).replace("分", ""))
                if score_num < low_score:
                    risks.append("分数较低，建议重点关注专科/高职优质专业")
            except (ValueError, TypeError):
                pass

        interest = _slot_value(slots, "interest")
        for r in high_risk:
            if r in interest:
                risks.append(f"「{interest}」属于需谨慎选择的专业方向，建议关注就业数据")
                break

    if not risks:
        risks.append("数据有限，建议以官方最新信息为准")

    if scene == "gaokao":
        risks.append("AI 输出仅用于辅助决策，不能替代省考试院和高校的官方招生信息")

    return risks


def _extract_next_actions(scene: str, slots: dict, data: dict) -> list[str]:
    """Extract concrete next steps."""
    actions: list[str] = []

    missing = [
        k for k in MISSING_SLOT_KEYS if not (_score_value(slots) if k == "score_rank" else _slot_value(slots, k))
    ]
    if missing:
        labels = {
            "province": "省份",
            "score_rank": "分数",
            "subject": "选科",
            "interest": "专业意向",
            "goal": "核心诉求",
        }
        action_text = "、".join(labels.get(m, m) for m in missing[:3])
        actions.append(f"补充{action_text}信息")

    if data.get("match_schools"):
        actions.append("对比推荐院校的录取数据和招生计划")
        actions.append("到省考试院官网核实最新录取信息")

    return actions


def _build_summary(scene: str, slots: dict, data: dict) -> str:
    """Build a one-line summary of the current analysis."""
    parts: list[str] = []
    province = _slot_value(slots, "province")
    score = _score_value(slots)
    interest = _slot_value(slots, "interest")

    if province:
        parts.append(province)
    if score:
        parts.append(str(score))
    if interest:
        parts.append(f"意向{interest}")

    if parts:
        return "，".join(parts) + "，规划分析中。"
    return "等待更多画像信息以生成精准规划。"
