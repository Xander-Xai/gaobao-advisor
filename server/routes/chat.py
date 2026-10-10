import json
import logging

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from config.loader import load_llm_config
from db.database import get_session
from db.models import Highlight
from server.auth import create_session_token, require_bearer_auth
from server.graph.graph import get_advisor_graph
from server.graph.nodes.llm_node import llm_node_stream
from server.privacy import safe_exception_name, safe_log_reference

logger = logging.getLogger(__name__)

_DEMO_DISCLOSURE = (
    "【社区演示模式】当前内容仅用于展示软件流程，数据均为合成示例；本项目是非官方工具，不能用于真实志愿决策。"
)

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

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Strip HTML tags from message input (XSS defense)."""
        import re

        # Strip HTML tags
        cleaned = re.sub(r"<[^>]+>", "", v)
        return cleaned.strip()


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

    # Phase 1: Run graph.
    # Keep this synchronous until the graph runtime itself is async-safe; the
    # previous thread-pool wrapper could deadlock under the current test/ASGI
    # environment and prevent SSE completion.
    try:
        result = graph.invoke(initial_state)
    except Exception:
        logger.exception("Phase 1 graph.invoke failed for %s", safe_log_reference(session_id))
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
        if load_llm_config().get("provider") == "demo":
            reply = f"{_DEMO_DISCLOSURE}\n\n{reply}"
            result["reply"] = reply
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

    # Emit quality scores after streaming completes
    qs = result.get("quality_scores", {})
    if qs:
        quality_event = {
            "type": "quality",
            "grade": result.get("quality_grade", "pass"),
            "rewritten": result.get("should_rewrite", False),
        }
        yield f"data: {json.dumps(quality_event)}\n\n"

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
async def submit_feedback(
    request: FeedbackRequest,
    authorization: str | None = Header(None),
):
    """提交用户反馈（有帮助/没帮助）"""
    require_bearer_auth(request.session_id, authorization)
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
    return {"success": False, "error": "保存反馈失败"}


class HighlightExtractRequest(BaseModel):
    """金句提取请求"""

    session_id: str = Field(..., min_length=4, max_length=64)
    content: str = Field(..., min_length=10)
    score: int = Field(default=0, ge=0, le=100)


@router.post("/chat/highlight")
async def submit_highlight(
    request: HighlightExtractRequest,
    authorization: str | None = Header(None),
):
    """提取金句"""
    require_bearer_auth(request.session_id, authorization)
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
        logger.error(
            "Highlight save failed for %s: %s",
            safe_log_reference(request.session_id),
            safe_exception_name(e),
        )
        return {"success": False, "error": "保存金句失败"}
