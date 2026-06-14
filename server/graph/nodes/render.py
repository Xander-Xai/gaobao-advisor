"""Render reply node — builds the final text response."""
from __future__ import annotations

from typing import Any

from server.graph.nodes.source_attribution import validate_source_attribution

# Disclaimer suffix appended to all advice
_DISCLAIMER = (
    "\n\n---\n"
    "声明：以上分析基于公开数据和AI模型，仅供参考。"
    "最终志愿填报请以各省教育考试院官方发布信息为准。"
)


def render_reply_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build the final reply text for the user.

    If a reply is already set (e.g. from question_generate or
    security_scan), pass it through unchanged.  Otherwise, assemble
    a reply from the structured result and reasoning.
    """
    # 如果 reply 已有,校验来源标注(在追加 disclaimer 前),然后追加 disclaimer
    existing_reply = state.get("reply", "")
    if existing_reply:
        try:
            existing_reply = validate_source_attribution(existing_reply)
        except Exception:
            # 校验失败不阻塞流程
            pass
        if "声明：以上分析基于" not in existing_reply:
            final_reply = existing_reply + _DISCLAIMER
        else:
            final_reply = existing_reply
        trace = list(state.get("trace", []))
        trace.append({"node": "render_reply", "event": "llm_reply_with_disclaimer"})
        return {"reply": final_reply, "trace": trace}

    scene = state.get("scene", "general")
    slots = state.get("slots", {})
    structured = state.get("structured_result", {})
    reasoning = state.get("reasoning", "")

    parts = []

    if scene == "gaokao":
        # Build gaokao-specific reply
        province = slots.get("province", "")
        score = slots.get("score", "")
        subject = slots.get("subject", "")
        interest = slots.get("interest", "")

        header = f"根据您提供的信息（{province}考生，{subject}，{score}分"
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
        interest = slots.get("interest", "")
        parts.append(f"关于{interest or '考研'}方向，以下是我的分析：")
        major = structured.get("major_analysis")
        if major and isinstance(major, dict):
            parts.append(str(major.get("description", ""))[:300])

    else:
        # Generic fallback
        parts.append("收到您的信息，以下是我的分析：")
        if reasoning:
            parts.append(reasoning[:500])

    # Phase 3: 先校验来源标注,再追加 disclaimer(避免 disclaimer 干扰标注)
    reply = "\n".join(parts)
    try:
        reply = validate_source_attribution(reply)
    except Exception:
        # 校验失败不阻塞流程
        pass
    reply = reply + _DISCLAIMER

    trace = list(state.get("trace", []))
    trace.append({"node": "render_reply", "event": "reply_built"})

    return {"reply": reply, "trace": trace}
