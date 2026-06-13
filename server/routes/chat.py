"""Chat endpoint with SSE streaming — backed by LangGraph workflow."""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.graph.graph import get_advisor_graph

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    scene: str = "gaokao"
    message: str = Field(..., min_length=1, max_length=3000)
    slots: dict | None = None


async def _sse_generator(
    session_id: str,
    scene: str,
    message: str,
    existing_slots: dict | None,
):
    """Yield SSE events for a chat response via the LangGraph pipeline."""
    graph = get_advisor_graph()
    initial_state = {
        "session_id": session_id,
        "input_text": message,
        "scene": scene,
        "slots": existing_slots or {},
        "messages": [],
        "trace": [],
    }
    result = graph.invoke(initial_state)

    # Emit updated slots
    if result.get("slots"):
        yield f"data: {json.dumps({'type': 'slots', 'data': result['slots']})}\n\n"

    # Emit emotion state
    if result.get("emotion_state"):
        yield f"data: {json.dumps({'type': 'emotion', 'state': result['emotion_state']})}\n\n"

    # Stream reply text in chunks
    reply = result.get("reply", "抱歉，暂时无法处理您的请求。")
    chunk_size = 20
    for i in range(0, len(reply), chunk_size):
        chunk = reply[i : i + chunk_size]
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

    # Emit structured result if present
    if result.get("structured_result"):
        yield f"data: {json.dumps({'type': 'structured', 'result': result['structured_result']})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'message_id': f'{session_id}-response'})}\n\n"


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
