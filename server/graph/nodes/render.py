"""Render reply node — builds the final text response."""

from __future__ import annotations

from typing import Any

# Disclaimer suffix appended to all advice
_DISCLAIMER = "\n\n---\n声明：以上分析基于公开数据和AI模型，仅供参考。最终志愿填报请以各省教育考试院官方发布信息为准。"


def _slot_value(slots: dict, *keys: str) -> str:
    """Read a slot value from flat or nested slot representations."""
    for key in keys:
        val = slots.get(key)
        if isinstance(val, dict):
            val = val.get("value", "")
        if val:
            return str(val)
    return ""


def _format_score(score: str) -> str:
    if not score:
        return ""
    return score if score.endswith("分") else f"{score}分"


def render_reply_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build the final reply text for the user.

    If a reply is already set (e.g. from question_generate or
    security_scan), pass it through unchanged.  Otherwise, assemble
    a reply from the structured result and reasoning.
    """
    # 如果 reply 已有,追加 disclaimer(来源标注由 source_attribution 节点处理)
    existing_reply = state.get("reply", "")
    if existing_reply:
        if "声明：以上分析基于" not in existing_reply:
            final_reply = existing_reply + _DISCLAIMER
        else:
            final_reply = existing_reply
        trace = list(state.get("trace", []))
        trace.append({"node": "render_reply", "event": "llm_reply_with_disclaimer"})
        return {
            "reply": final_reply,
            "trace": trace,
            "rewrite_attempts": state.get("rewrite_attempts", 0) + (1 if state.get("should_rewrite") else 0),
        }

    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    structured = state.get("structured_result", {})
    reasoning = state.get("reasoning", "")

    parts = []

    if scene == "gaokao":
        # Build gaokao-specific reply
        province = _slot_value(slots, "province")
        score = _format_score(_slot_value(slots, "score_rank", "score"))
        subject = _slot_value(slots, "subject")
        interest = _slot_value(slots, "interest")

        profile_bits = []
        if province:
            profile_bits.append(f"{province}考生")
        if subject:
            profile_bits.append(subject)
        if score:
            profile_bits.append(score)
        profile_text = "，".join(profile_bits) if profile_bits else "当前画像信息"
        header = f"根据您提供的信息（{profile_text}"
        if interest:
            header += f"，意向专业：{interest}"
        header += "），我为您分析如下："
        parts.append(header)

        matched = structured.get("matched_schools", [])
        if matched:
            parts.append("\n推荐院校：")
            for i, s in enumerate(matched[:5], 1):
                name = s.get("name", "")
                line = s.get("score_line", "")
                parts.append(f"{i}. {name}（录取线参考：{line}分）")

        rank = structured.get("rank_analysis")
        if rank:
            parts.append(f"\n分数位次分析：{rank}")

        major = structured.get("major_analysis")
        if major and isinstance(major, dict):
            parts.append(f"\n专业信息：{major.get('description', str(major)[:200])}")

    elif scene == "kaoyan":
        interest = _slot_value(slots, "interest")
        parts.append(f"关于{interest or '考研'}方向，以下是我的分析：")
        major = structured.get("major_analysis")
        if major and isinstance(major, dict):
            parts.append(str(major.get("description", ""))[:300])

    else:
        # Generic fallback
        parts.append("收到您的信息，以下是我的分析：")
        if reasoning:
            parts.append(reasoning[:500])

    # 先构建回复,再追加 disclaimer(来源标注由 source_attribution 节点处理)
    reply = "\n".join(parts)
    reply = reply + _DISCLAIMER

    trace = list(state.get("trace", []))
    trace.append({"node": "render_reply", "event": "reply_built"})

    return {
        "reply": reply,
        "trace": trace,
        "rewrite_attempts": state.get("rewrite_attempts", 0) + (1 if state.get("should_rewrite") else 0),
    }
