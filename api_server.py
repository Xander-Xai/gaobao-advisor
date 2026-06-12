"""
高报Agent · API 服务器
提供 RESTful 接口供 H5/小程序调用。
启动方式: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import sys
import json
import uuid
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ratelimit import RateLimiter

# 延迟导入 agent 模块（避免启动时加载全部依赖）
from agent import GaokaoAdvisor, SLOTS, filled_slots

app = FastAPI(title="高报Agent API", version="1.0.0")

# 进程级限流器（解决多 tab 绕过限流的竞态问题）
_api_rate_limiter = RateLimiter(
    hourly_limit=20,
    daily_limit=40,
    max_input_len=500,
)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """HTTP 中间件：基于客户端 IP 的令牌桶限流。"""
    client_ip = request.client.host if request.client else "unknown"
    allowed, reason = _api_rate_limiter.check(client_ip, msg_length=0)
    if not allowed:
        logging.warning("rate_limit_exceeded ip=%s reason=%s", client_ip, reason)
        return JSONResponse(
            status_code=429,
            content={"error": "请求过于频繁，请稍后再试", "detail": reason},
        )
    return await call_next(request)

# CORS 支持（H5 页面跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务（H5 前端）
H5_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h5")
if os.path.isdir(H5_DIR):
    app.mount("/h5", StaticFiles(directory=H5_DIR, html=True), name="h5")


@app.get("/")
async def root():
    """首页 — 自动跳转到 H5 聊天页面。"""
    index_path = os.path.join(H5_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "高报Agent API 已启动", "docs": "/docs", "health": "/api/health"}

# ── 请求/响应模型 ──

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # 可选，用于恢复对话


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    slots: dict  # 当前槽位状态


class ResetRequest(BaseModel):
    session_id: str


# ── 全局 advisor 池（按 session_id 管理）──
_advisors: dict[str, GaokaoAdvisor] = {}
_session_timestamps: dict[str, float] = {}  # session_id -> last access time

# 最大并发会话数（防止内存无限增长）
MAX_SESSIONS = 500

# 会话最大空闲时间（秒），超时后自动淘汰
SESSION_TTL = 1800  # 30 minutes


def _get_advisor(session_id: str) -> GaokaoAdvisor:
    """获取或创建 advisor 实例。超过上限或 TTL 超时则淘汰。"""
    global _advisors, _session_timestamps
    now = time.time()

    # 淘汰所有超时的会话（TTL 过期）
    expired = [
        sid for sid, ts in _session_timestamps.items() if now - ts > SESSION_TTL
    ]
    for sid in expired:
        _advisors.pop(sid, None)
        _session_timestamps.pop(sid, None)
        logging.info("session_expired sid=%s (TTL exceeded)", sid)

    # LRU 淘汰：超过上限时清除最久未访问的会话
    if len(_advisors) >= MAX_SESSIONS and session_id not in _advisors:
        oldest_sid = min(_session_timestamps, key=_session_timestamps.get)
        _advisors.pop(oldest_sid, None)
        _session_timestamps.pop(oldest_sid, None)
        logging.info("session_evicted sid=%s (pool full)", oldest_sid)

    if session_id not in _advisors:
        _advisors[session_id] = GaokaoAdvisor(
            api_key=os.environ.get("LLM_API_KEY", ""),
            slots={k: dict(v) for k, v in SLOTS.items()},
        )
    _session_timestamps[session_id] = now
    return _advisors[session_id]


# ── 接口 ──

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """同步聊天接口。"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    sid = req.session_id or uuid.uuid4().hex
    advisor = _get_advisor(sid)
    reply = advisor.chat(req.message)
    return ChatResponse(reply=reply, session_id=sid, slots=advisor.slots)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式聊天接口，逐步返回 AI 回复。

    事件格式:
        data: {"chunk": "部分文本"}\n\n
        data: {"done": true, "reply": "完整回复", "slots": {...}}\n\n
        data: [DONE]\n\n
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    sid = req.session_id or uuid.uuid4().hex
    advisor = _get_advisor(sid)

    def event_stream():
        for chunk in advisor.chat_stream(req.message):
            if chunk.startswith("|||FINAL|||"):
                final_reply = chunk[len("|||FINAL|||"):]
                done_payload = json.dumps({
                    "done": True,
                    "reply": final_reply,
                    "slots": advisor.slots,
                }, ensure_ascii=False)
                yield f"data: {done_payload}\n\n"
            else:
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@app.get("/api/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok", "active_sessions": len(_advisors)}


@app.post("/api/reset")
async def reset(req: ResetRequest):
    """重置指定会话的对话和槽位。"""
    if req.session_id in _advisors:
        _advisors[req.session_id].reset()
        return {"status": "reset", "session_id": req.session_id}
    raise HTTPException(status_code=404, detail="session_id 不存在")


@app.get("/api/slots/{session_id}")
async def get_slots(session_id: str):
    """获取指定会话的槽位状态。"""
    if session_id in _advisors:
        return {"session_id": session_id, "slots": _advisors[session_id].slots}
    raise HTTPException(status_code=404, detail="session_id 不存在")
