"""Chat endpoint with SSE streaming — backed by LangGraph workflow."""

import asyncio
import json
import logging
import re
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db.crud import get_or_create_conversation, load_conversation_slots
from db.database import get_session
from db.models import Highlight
from server.auth import create_session_token, verify_session_token
from server.graph.graph import get_advisor_graph, get_post_generation_graph
from server.graph.nodes.llm_node import llm_node_stream
from server.graph.nodes.memory import memory_node
from server.graph.nodes.render import ensure_disclaimer, render_reply_node
from server.graph.nodes.source_attribution import validate_source_attribution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])
_SENTENCE_BOUNDARY = re.compile(r"[。！？\n]")
_STREAM_END = object()


def _require_session_auth(session_id: str, authorization: str | None) -> None:
    """Require a valid Bearer token bound to the requested session."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_session_token(session_id, token):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")


class SessionCreateRequest(BaseModel):
    scene: str = Field(default="gaokao", min_length=1, max_length=32)


@router.post("/session")
async def create_chat_session(request: SessionCreateRequest):
    """Create a server-owned session and return its ownership token."""
    session_id = f"session-{uuid.uuid4().hex}"
    db = get_session()
    try:
        get_or_create_conversation(db, session_id)
    except Exception:
        logger.exception("Failed to create chat session")
        raise HTTPException(status_code=503, detail="Unable to create session") from None
    finally:
        db.close()

    return {
        "session_id": session_id,
        "session_token": create_session_token(session_id),
        "scene": request.scene,
    }


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
    """Load persisted slots and query state for a chat turn."""
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


async def _iter_llm_stream(state: dict):
    """Adapt the synchronous OpenAI stream to an async iterator without blocking the event loop."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer() -> None:
        try:
            for item in llm_node_stream(state):
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:
            logger.exception("Unexpected LLM stream producer failure")
            loop.call_soon_threadsafe(queue.put_nowait, ("", True))
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _STREAM_END)

    producer_task = asyncio.create_task(asyncio.to_thread(producer))
    try:
        while True:
            item = await queue.get()
            if item is _STREAM_END:
                break
            if isinstance(item, Exception):
                continue
            yield item
    finally:
        await producer_task


def _merge_node_result(state: dict, update: dict) -> dict:
    merged = dict(state)
    merged.update(update or {})
    return merged


async def _run_post_generation(result: dict) -> dict:
    """Run post-generation checks and persistence after the final reply exists.

    If the quality pipeline fails (for example, the judge provider is down),
    still persist the conversation exactly once.
    """
    post_graph = get_post_generation_graph()
    try:
        return await asyncio.to_thread(post_graph.invoke, result)
    except Exception:
        logger.exception("Post-generation pipeline failed for session %s", result.get("session_id"))
        try:
            memory_update = await asyncio.to_thread(memory_node, result)
            return _merge_node_result(result, memory_update)
        except Exception:
            logger.exception("Fallback memory persistence failed for session %s", result.get("session_id"))
            return result


async def _sse_generator(
    session_id: str,
    scene: str,
    message: str,
    existing_slots: dict | None,
):
    """Yield SSE events for a chat response via pre-generation → stream → post-generation."""
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
        logger.exception("Pre-generation graph.invoke failed for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'code': 'GRAPH_FAILED', 'message': '服务暂时不可用，请稍后重试'})}\n\n"
        return

    if result.get("slots"):
        yield f"data: {json.dumps({'type': 'slots', 'data': result['slots']})}\n\n"

    if result.get("emotion_state"):
        yield f"data: {json.dumps({'type': 'emotion', 'state': result['emotion_state']})}\n\n"

    if result.get("structured_result"):
        yield f"data: {json.dumps({'type': 'structured', 'result': result['structured_result']})}\n\n"

    # Direct replies are reserved for security blocks and profile questions.
    if result.get("reply"):
        rendered = render_reply_node(result)
        result = _merge_node_result(result, rendered)
        result["reply"] = validate_source_attribution(result["reply"])
        result = await _run_post_generation(result)

        reply = result.get("reply", "")
        for i in range(0, len(reply), 20):
            chunk = reply[i : i + 20]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    else:
        # Main answer path: stream the LLM first, then run post-generation checks.
        full_reply: list[str] = []
        sentence_buffer = ""
        degraded = False

        async for token, is_degraded in _iter_llm_stream(result):
            degraded = degraded or is_degraded
            sentence_buffer += token

            while True:
                match = _SENTENCE_BOUNDARY.search(sentence_buffer)
                if not match:
                    break
                end = match.end()
                sentence = sentence_buffer[:end]
                sentence_buffer = sentence_buffer[end:]
                attributed = validate_source_attribution(sentence)
                full_reply.append(attributed)
                yield f"data: {json.dumps({'type': 'token', 'content': attributed})}\n\n"

        if sentence_buffer:
            attributed = validate_source_attribution(sentence_buffer)
            full_reply.append(attributed)
            yield f"data: {json.dumps({'type': 'token', 'content': attributed})}\n\n"

        reply_without_disclaimer = "".join(full_reply)
        final_reply = ensure_disclaimer(reply_without_disclaimer)
        disclaimer_suffix = final_reply[len(reply_without_disclaimer) :]
        if disclaimer_suffix:
            yield f"data: {json.dumps({'type': 'token', 'content': disclaimer_suffix})}\n\n"

        result["reply"] = final_reply
        result["degraded"] = degraded
        result = await _run_post_generation(result)

        if degraded:
            yield f"data: {json.dumps({'type': 'degraded', 'message': 'AI 服务暂时不稳定，已启用降级回复'})}\n\n"

    if result.get("quality_grade"):
        yield f"data: {json.dumps({'type': 'quality', 'grade': result['quality_grade'], 'rewritten': bool(result.get('needs_rewrite'))})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'message_id': f'{session_id}-response', 'session_token': create_session_token(session_id)})}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(None)):
    _require_session_auth(request.session_id, authorization)
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
async def submit_feedback(request: FeedbackRequest, authorization: str | None = Header(None)):
    """提交用户反馈（有帮助/没帮助）"""
    _require_session_auth(request.session_id, authorization)
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
async def submit_highlight(request: HighlightExtractRequest, authorization: str | None = Header(None)):
    """提取金句"""
    _require_session_auth(request.session_id, authorization)
    db = get_session()
    try:
        hl = Highlight(
            session_id=request.session_id,
            content=request.content,
            score=request.score,
        )
        db.add(hl)
        db.commit()
        return {"success": True}
    except Exception:
        logger.exception("Highlight persistence failed for session %s", request.session_id)
        return {"success": False, "error": "Failed to save highlight"}
    finally:
        db.close()
