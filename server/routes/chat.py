"""Chat endpoint with SSE streaming — backed by LangGraph workflow."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


async def _sse_generator(
    session_id: str,
    scene: str,
    message: str,
    existing_slots: dict | None,
):
    """Yield SSE events for a chat response via the LangGraph pipeline.

    Two-phase streaming:
    1. Run graph up to LLM node (yields metadata: slots, emotion, structured)
    2. Stream LLM tokens in real-time via llm_node_stream

    The final 'done' event returns a session_token for Bearer auth
    on subsequent requests (profile/voice endpoints).
    """
    graph = get_advisor_graph()
    initial_state = {
        "session_id": session_id,
        "input_text": message,
        "scene": scene,
        "slots": existing_slots or {},
        "messages": [],
        "trace": [],
    }

    # Phase 1: Run graph (synchronous, offloaded to thread)
    try:
        result = await asyncio.to_thread(graph.invoke, initial_state)
    except Exception:
        logger.exception("Phase 1 graph.invoke failed for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'code': 'GRAPH_FAILED', 'message': '服务暂时不可用，请稍后重试'})}\n\n"
        return

    # Emit updated slots
    if result.get("slots"):
        yield f"data: {json.dumps({'type': 'slots', 'data': result['slots']})}\n\n"

    # Emit emotion state
    if result.get("emotion_state"):
        yield f"data: {json.dumps({'type': 'emotion', 'state': result['emotion_state']})}\n\n"

    # Emit structured result if present
    if result.get("structured_result"):
        yield f"data: {json.dumps({'type': 'structured', 'result': result['structured_result']})}\n\n"

    # Phase 2: Stream LLM tokens in real-time
    if result.get("reply"):
        # Non-LLM reply (security block, question generation): emit in chunks
        reply = result["reply"]
        chunk_size = 20
        for i in range(0, len(reply), chunk_size):
            chunk = reply[i : i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    else:
        # LLM reply: stream tokens one by one
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
