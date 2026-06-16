"""Report API routes — generate, retrieve, and export advisory reports.

Report generation reads the user's real conversation data (slots + last AI reply)
from the database, NOT hardcoded placeholder values.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Response
from pydantic import BaseModel

from server.report.cover import CoverGenerator
from server.report.exporter import ReportExporter
from server.report.generator import ReportGenerator
from server.report.models import Report
from server.report.storage import ReportStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["report"])

_storage = ReportStorage()


class GenerateRequest(BaseModel):
    """Request body for report generation."""

    session_id: str
    student_name: str | None = None


class GenerateResponse(BaseModel):
    """Response body for report generation."""

    report_id: str
    status: str
    message: str


def _load_session_slots(session_id: str) -> dict:
    """Load slot data from the conversation database.

    Returns the raw slots dict (may be nested {"value": ..., "filled": True}
    format or flat string format), or empty dict if not found.
    """
    from db.crud import load_conversation_slots
    from db.database import get_session

    db = get_session()
    try:
        slots = load_conversation_slots(db, session_id)
        return slots or {}
    except Exception:
        logger.warning("Failed to load slots for session %s", session_id)
        return {}
    finally:
        db.close()


def _load_last_ai_reply(session_id: str) -> str:
    """Load the last AI assistant reply from the conversation history.

    Returns the text content of the most recent assistant message,
    or empty string if not found.
    """
    from db.crud import load_conversation_history
    from db.database import get_session

    db = get_session()
    try:
        messages = load_conversation_history(db, session_id)
        # Walk backwards to find the last assistant message
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"]
        return ""
    except Exception:
        logger.warning("Failed to load history for session %s", session_id)
        return ""
    finally:
        db.close()


def _parse_facts_from_slots(slots: dict) -> list[str]:
    """Extract factual statements from slot data."""
    facts: list[str] = []
    slot_labels = {
        "province": "省份",
        "score": "分数",
        "score_rank": "分数",
        "subject": "选科",
        "interest": "专业意向",
        "region": "地域偏好",
        "family": "家庭背景",
        "goal": "核心诉求",
    }
    for key, label in slot_labels.items():
        val = slots.get(key, "")
        if isinstance(val, dict):
            val = val.get("value", "")
        if val:
            facts.append(f"{label}：{val}")
    return facts


def _parse_suggestions_from_reply(reply: str) -> list[str]:
    """Extract school/major suggestions from the AI reply text.

    Looks for lines that contain recommendation patterns like:
    - "推荐：XXX"
    - "冲刺/稳妥/保底：XXX"
    - Numbered recommendation items
    """
    suggestions: list[str] = []
    if not reply:
        return suggestions

    lines = reply.split("\n")
    for line in lines:
        stripped = line.strip()
        # Match lines with recommendation markers
        if any(marker in stripped for marker in ["推荐", "冲刺", "稳妥", "保底", "保底"]):
            # Clean up markdown/bullet formatting
            clean = re.sub(r"^[\d\-\*•\.、]+\s*", "", stripped)
            if clean and len(clean) > 2:
                suggestions.append(clean)
        # Also match numbered school entries (e.g., "1. 山东大学")
        elif re.match(r"^\d+[\.\、]\s*.+大[学院]", stripped):
            clean = re.sub(r"^\d+[\.\、]\s*", "", stripped)
            if clean:
                suggestions.append(clean)

    return suggestions[:10] if suggestions else []


def _parse_risks_from_reply(reply: str) -> list[str]:
    """Extract risk warnings from the AI reply text."""
    risks: list[str] = []
    if not reply:
        return risks

    lines = reply.split("\n")
    in_risk_section = False
    for line in lines:
        stripped = line.strip()
        # Detect risk section headers
        if any(marker in stripped for marker in ["风险", "注意", "提醒", "⚠"]):
            if len(stripped) < 15:
                in_risk_section = True
                continue
            # Inline risk on the same line as the marker
            clean = re.sub(r"^[\-\*•\.、]+\s*", "", stripped)
            if clean and len(clean) > 3:
                risks.append(clean)
            in_risk_section = True
        elif in_risk_section and stripped:
            # Stop if we hit another section
            if any(marker in stripped for marker in ["建议", "推荐", "院校", "📌", "📋", "🎯"]):
                in_risk_section = False
                continue
            clean = re.sub(r"^[\d\-\*•\.、]+\s*", "", stripped)
            if clean and len(clean) > 3:
                risks.append(clean)

    return risks if risks else ["数据有限，建议以官方最新信息为准"]


def _parse_next_actions_from_reply(reply: str) -> list[str]:
    """Extract next action items from the AI reply text."""
    actions: list[str] = []
    if not reply:
        return actions

    lines = reply.split("\n")
    in_action_section = False
    for line in lines:
        stripped = line.strip()
        # Detect action section headers
        if any(marker in stripped for marker in ["建议行动", "下一步", "行动建议", "📌"]):
            if len(stripped) < 15:
                in_action_section = True
                continue
            clean = re.sub(r"^[\d\-\*•\.、]+\s*", "", stripped)
            if clean and len(clean) > 3:
                actions.append(clean)
            in_action_section = True
        elif in_action_section and stripped:
            # Stop at next section
            if any(marker in stripped for marker in ["风险", "推荐", "院校", "⚠", "📋", "🎯"]):
                in_action_section = False
                continue
            clean = re.sub(r"^[\d\-\*•\.、]+\s*", "", stripped)
            if clean and len(clean) > 3:
                actions.append(clean)

    return actions if actions else ["补充省份、分数、选科等信息以获得更精准推荐"]


def _build_summary(slots: dict) -> str:
    """Build a one-line summary from slot data."""
    parts: list[str] = []

    def _get(key: str) -> str:
        val = slots.get(key, "")
        if isinstance(val, dict):
            val = val.get("value", "")
        return str(val) if val else ""

    province = _get("province")
    score = _get("score") or _get("score_rank")
    subject = _get("subject")
    interest = _get("interest")

    if province:
        parts.append(province)
    if score:
        parts.append(f"{score}分")
    if interest:
        parts.append(f"意向{interest}")

    if parts:
        return "，".join(parts) + "，志愿规划分析报告。"
    return "高考志愿填报分析报告"


@router.post("/report/generate", response_model=GenerateResponse)
async def generate_report(body: GenerateRequest):
    """Generate a report from the user's real conversation data.

    Reads slots (province, score, subject, interest) and the last AI reply
    from the database to produce a personalized advisory report.
    """
    session_id = body.session_id

    # 1. Load real data from conversation database
    slots = _load_session_slots(session_id)
    last_reply = _load_last_ai_reply(session_id)

    # 2. Extract structured content from real data
    facts = _parse_facts_from_slots(slots)
    suggestions = _parse_suggestions_from_reply(last_reply)
    risks = _parse_risks_from_reply(last_reply)
    next_actions = _parse_next_actions_from_reply(last_reply)
    summary = _build_summary(slots)

    # 3. Build the Report from real data
    report = ReportGenerator.from_card(
        card=None,  # Not using StructuredPlanningCard — data comes from slots + reply
        session_id=session_id,
        slots=slots,
        student_name=body.student_name,
    )

    # Override with parsed content from real conversation
    report.summary = summary
    report.facts = facts
    report.suggestions = suggestions
    report.risks = risks
    report.next_actions = next_actions

    # Calculate confidence based on profile completeness
    filled = sum(1 for f in ("province", "score", "subject", "interest") if slots.get(f))
    report.confidence = round(filled / 4, 2) if filled else 0.0

    # 4. Save and return
    _storage.save(report)
    logger.info(
        "Report generated: %s for session %s (confidence=%.0f%%, facts=%d, suggestions=%d)",
        report.id,
        session_id,
        report.confidence * 100,
        len(facts),
        len(suggestions),
    )

    return GenerateResponse(
        report_id=report.id,
        status="completed",
        message="报告已生成",
    )


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    """Return report data as a JSON dict."""
    report = _storage.load(report_id)
    if report is None:
        return Response(
            content='{"error": "报告不存在"}',
            media_type="application/json",
            status_code=404,
        )
    return report.to_dict()


@router.get("/report/{report_id}/html")
async def get_report_html(report_id: str):
    """Return the full HTML report page."""
    report = _storage.load(report_id)
    if report is None:
        return Response(content="报告不存在", status_code=404)
    html = ReportExporter.to_html(report)
    return Response(content=html, media_type="text/html")


@router.get("/report/{report_id}/cover.svg")
async def get_report_cover_svg(report_id: str):
    """Return the SVG cover image for a report."""
    report = _storage.load(report_id)
    if report is None:
        return Response(content="报告不存在", status_code=404)
    svg = CoverGenerator.generate_svg(report)
    return Response(content=svg, media_type="image/svg+xml")
