"""Chat endpoint with SSE streaming — backed by LangGraph workflow."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db.crud import load_conversation_slots
from db.database import get_session
from db.models import Highlight
from server.auth import create_session_token
from server.graph.graph import get_advisor_graph
from server.graph.nodes.llm_node import llm_node_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=4,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="会话ID：4-64位字母数字下划线连字符",
    )
    scene: str = "gaokao"
    message: str = Field(..., min_length=1, max_length=3000)
    slots: dict | None = None


def _load_persisted_state(session_id: str) -> tuple[dict, dict]:
    """Load persisted slots and query state for a chat turn.

    Keeping this server-side avoids relying on the frontend to echo every slot
    on every request and lets soul-query round tracking survive reconnects.
    """
    db = get_session()
    try:
        persisted = load_conversation_slots(db, session_id) or {}
    except Exception:
        logger.warning("Failed to hydrate session slots for %s", session_id, exc_info=True)
        return {}, {}
    finally:
        db.close()

    query_state = persisted.get("_query_state", {})
    slots = {key: value for key, value in persisted.items() if key != "_query_state"}
    return slots, query_state if isinstance(query_state, dict) else {}


async def _sse_generator(
    session_id: str,
    scene: str,
    message: str,
    existing_slots: dict | None,
):
    """Yield SSE events for a chat response via the LangGraph pipeline."""
    graph = get_advisor_graph()
    persisted_slots, query_state = _load_persisted_state(session_id)
    merged_slots = dict(persisted_slots)
    merged_slots.update(existing_slots or {})

    initial_state = {
        "session_id": session_id,
        "input_text": message,
        "scene": scene,
        "slots": merged_slots,
        "_query_state": query_state,
        "messages": [],
        "trace": [],
    }

    try:
        result = await asyncio.to_thread(graph.invoke, initial_state)
    except Exception:
        logger.exception("Phase 1 graph.invoke failed for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'code': 'GRAPH_FAILED', 'message': '服务暂时不可用，请稍后重试'})}\n\n"
        return

    if result.get("slots"):
        yield f"data: {json.dumps({'type': 'slots', 'data': result['slots']})}\n\n"

    if result.get("emotion_state"):
        yield f"data: {json.dumps({'type': 'emotion', 'state': result['emotion_state']})}\n\n"

    if result.get("structured_result"):
        yield f"data: {json.dumps({'type': 'structured', 'result': result['structured_result']})}\n\n"

    if result.get("reply"):
        reply = result["reply"]
        chunk_size = 20
        for i in range(0, len(reply), chunk_size):
            chunk = reply[i : i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    else:
        full_reply = []
        degraded = False
        for token, is_degraded in llm_node_stream(result):
            full_reply.append(token)
            degraded = is_degraded
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        result["reply"] = "".join(full_reply)
        if degraded:
            yield f"data: {json.dumps({'type': 'degraded', 'message': 'AI 服务暂时不稳定，已启用降级回复'})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'message_id': f'{session_id}-response', 'session_token': create_session_token(session_id)})}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        _sse_generator(
            request.session_id,
            request.scene,
            request.message,
            request.slots,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class FeedbackRequest(BaseModel):
    """用户反馈请求"""

    session_id: str = Field(..., min_length=4, max_length=64)
    message_index: int = Field(..., ge=0)
    rating: str = Field(..., pattern=r"^(helpful|not_helpful)$")
    feedback_text: str | None = None
    quality_score_id: int | None = None


@router.post("/chat/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交用户反馈（有帮助/没帮助）"""
    from server.quality.feedback import FeedbackCollector

    collector = FeedbackCollector()
    ok = collector.save_feedback(
        conversation_id=request.session_id,
        message_index=request.message_index,
        rating=request.rating,
        feedback_text=request.feedback_text,
        quality_score_id=request.quality_score_id,
    )
    if ok:
        return {"success": True}
    return {"success": False, "error": "Failed to save feedback"}


class HighlightExtractRequest(BaseModel):
    """金句提取请求"""

    session_id: str = Field(..., min_length=4, max_length=64)
    content: str = Field(..., min_length=10)
    score: int = Field(default=0, ge=0, le=100)


@router.post("/chat/highlight")
async def submit_highlight(request: HighlightExtractRequest):
    """提取金句"""
    try:
        hl = Highlight(
            session_id=request.session_id,
            content=request.content,
            score=request.score,
        )
        db = get_session()
        db.add(hl)
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        logger.error(f"Highlight error: {e}")
        return {"success": False, "error": str(e)}
