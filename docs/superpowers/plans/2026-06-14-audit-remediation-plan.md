# Gaobao Advisor 审计修复实现规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-06-14 多角色审计中发现的 6 个跨角色交叉命中问题和 22 项自查表中未通过的 P0/P1 项，将项目从"有条件通过"推进到"可上线"状态。

**Architecture:** 分两个阶段执行：Phase A（6 个 P0 阻塞项，预计 2-3 天）和 Phase B（8 个 P1 高优项，预计 3-5 天）。每个 Task 遵循 TDD 模式，先写测试再实现。修改集中在 `server/`（后端）、`frontend/`（Vue SPA）、`tests/`（测试）、`nginx.conf`（安全头）。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, pytest, Vue 3, DOMPurify, Vitest, ruff, GitHub Actions

---

## 文件结构总览

### Phase A — P0 阻塞项

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/auth.py` | **新建** | HMAC session token 生成与验证 |
| `server/routes/chat.py` | 修改 | 创建会话时签发 token |
| `server/routes/profile.py` | 修改 | 端点添加 token 验证 |
| `server/graph/graph.py` | 修改 | 移除 `llm_reason` 节点（双重 LLM 修复） |
| `server/routes/chat.py` | 修改 | SSE 流直接调用 `llm_node_stream` |
| `server/graph/nodes/llm_node.py` | 修改 | 修复 logging bug（`_maybe_trim`） |
| `frontend/package.json` | 修改 | 添加 `dompurify` 依赖 |
| `frontend/src/components/chat/MessageBubble.vue` | 修改 | `v-html` 添加 DOMPurify 净化 |
| `frontend/src/utils/sanitize.js` | **新建** | HTML 净化工具函数 |
| `nginx.conf` | 修改 | 添加安全响应头 |
| `pyproject.toml` | 修改 | 添加 `--cov` 配置 |
| `.github/workflows/ci.yml` | 修改 | 添加覆盖率步骤 |
| `CONVENTIONS.md` | **新建** | 工程约束文件 |

### Phase B — P1 高优项

| 文件 | 操作 | 职责 |
|------|------|------|
| `db/crud.py` | 修改 | N+1 查询修复（joinedload） |
| `server/middleware/ratelimit.py` | 修改 | TTL 驱逐机制 |
| `server/middleware/security.py` | 修改 | 统一 SSRF/injection 到 `utils.py` |
| `utils.py` | 修改 | 统一安全函数 |
| `db/database.py` | 修改 | SQLite WAL 模式 |
| `tests/conftest.py` | 修改 | 共享 fixtures |
| `tests/` (多个) | 修改 | silent exception 添加日志 |
| `ruff format .` | 命令 | 全量格式化 |

---

## Phase A — P0 阻塞项修复

---

### Task 1: Session 认证 — HMAC Token 生成与验证

**Files:**
- Create: `server/auth.py`
- Create: `tests/test_auth.py`
- Modify: `server/routes/chat.py:28-81`
- Modify: `server/routes/profile.py:41-107`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_auth.py`:

```python
"""Tests for session HMAC token authentication."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.auth import create_session_token, verify_session_token


class TestSessionToken:
    def test_create_returns_string(self):
        token = create_session_token("session-123456")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        token = create_session_token("session-123456")
        result = verify_session_token("session-123456", token)
        assert result is True

    def test_verify_wrong_session_id(self):
        token = create_session_token("session-123456")
        result = verify_session_token("session-999999", token)
        assert result is False

    def test_verify_tampered_token(self):
        token = create_session_token("session-123456")
        tampered = token[:-4] + "XXXX"
        result = verify_session_token("session-123456", tampered)
        assert result is False

    def test_verify_empty_token(self):
        result = verify_session_token("session-123456", "")
        assert result is False

    def test_verify_none_token(self):
        result = verify_session_token("session-123456", None)
        assert result is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_auth.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'server.auth'`

- [ ] **Step 3: 实现最小代码**

创建 `server/auth.py`:

```python
"""Session HMAC token authentication — lightweight session ownership proof.

No full auth system needed: the client receives a signed token on first
contact and must present it on subsequent requests. Prevents session_id
enumeration attacks.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

_SECRET = os.getenv("SESSION_SECRET", "")


def _get_secret() -> bytes:
    """Return the HMAC signing secret, generating one if not configured."""
    global _SECRET
    if not _SECRET:
        _SECRET = secrets.token_hex(32)
    return _SECRET.encode()


def create_session_token(session_id: str) -> str:
    """Create an HMAC-SHA256 token for the given session_id."""
    secret = _get_secret()
    return hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()


def verify_session_token(session_id: str, token: str | None) -> bool:
    """Verify the token matches the session_id. Returns False on any error."""
    if not session_id or not token:
        return False
    try:
        expected = create_session_token(session_id)
        return hmac.compare_digest(expected, token)
    except Exception:
        return False
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_auth.py -v
```

预期：6 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/auth.py tests/test_auth.py
git commit -m "feat: add HMAC session token auth for session ownership proof"
```

---

### Task 2: Chat 端点签发 Token + Profile 端点验证

**Files:**
- Modify: `server/routes/chat.py:15-95`
- Modify: `server/routes/profile.py:41-107`
- Create: `tests/test_auth_endpoints.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_auth_endpoints.py`:

```python
"""Tests for auth integration in chat and profile endpoints."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


class TestChatTokenIssuance:
    def test_chat_returns_session_token_in_done_event(self):
        """Chat SSE response should include a session_token in the done event."""
        response = client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-auth-001",
                "message": "你好",
                "scene": "gaokao",
            },
        )
        # Collect SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                import json
                events.append(json.loads(line[6:]))
        # The 'done' event should contain session_token
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
        assert "session_token" in done_events[0]


class TestProfileAuth:
    def test_profile_without_token_returns_401(self):
        """Profile GET without token should return 401."""
        response = client.get("/api/v1/profile/test-auth-001")
        assert response.status_code == 401

    def test_profile_with_valid_token_returns_200(self):
        """Profile GET with valid token should return 200."""
        from server.auth import create_session_token
        token = create_session_token("test-auth-001")
        response = client.get(
            "/api/v1/profile/test-auth-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_profile_with_invalid_token_returns_401(self):
        """Profile GET with invalid token should return 401."""
        response = client.get(
            "/api/v1/profile/test-auth-001",
            headers={"Authorization": "Bearer invalid-token-xxx"},
        )
        assert response.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_auth_endpoints.py -v
```

预期：FAIL — done event 无 session_token, profile 无 401

- [ ] **Step 3: 修改 chat.py — 签发 token**

在 `server/routes/chat.py` 中，修改 `_sse_generator` 函数，在 `done` 事件中包含 token：

```python
"""Chat endpoint with SSE streaming — backed by LangGraph workflow."""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.auth import create_session_token
from server.graph.graph import get_advisor_graph
from server.graph.nodes.llm_node import llm_node_stream

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
    result = await asyncio.to_thread(graph.invoke, initial_state)

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
        for token in llm_node_stream(result):
            full_reply.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        result["reply"] = "".join(full_reply)

    # Issue session token for ownership proof
    session_token = create_session_token(session_id)
    yield f"data: {json.dumps({'type': 'done', 'message_id': f'{session_id}-response', 'session_token': session_token})}\n\n"


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
```

- [ ] **Step 4: 修改 profile.py — 添加 token 验证**

在 `server/routes/profile.py` 中添加 token 验证依赖：

```python
"""Profile endpoints — user profiling via soul query engine.

Endpoints:
- GET  /api/v1/profile/{session_id}     → current profile + completeness
- PUT  /api/v1/profile/{session_id}     → update single field
- GET  /api/v1/profile/{session_id}/next-question → next question
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from server.auth import verify_session_token
from server.deps import get_soul_query_engine
from server.soul_query import QueryState
from server.user_profile import UserProfile, load_profile, save_profile

router = APIRouter(prefix="/api/v1", tags=["profile"])


def _require_auth(session_id: str, authorization: str | None = None) -> None:
    """Validate session ownership via Bearer token. Raises 401 on failure."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_session_token(session_id, token):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")


class ProfileUpdateRequest(BaseModel):
    field: str = Field(..., min_length=1, max_length=32)
    value: str = Field(..., min_length=1, max_length=200)


class ProfileResponse(BaseModel):
    session_id: str
    profile: dict
    is_complete: bool
    missing_fields: list[str]


class NextQuestionResponse(BaseModel):
    session_id: str
    question: str | None
    round_count: int
    is_complete: bool


class SkipFieldRequest(BaseModel):
    field: str = Field(..., min_length=1, max_length=32)


@router.get("/profile/{session_id}", response_model=ProfileResponse)
async def get_profile(session_id: str, authorization: str | None = Header(None)):
    """Get current user profile and completeness status."""
    _require_auth(session_id, authorization)
    profile = load_profile(session_id)
    return ProfileResponse(
        session_id=session_id,
        profile=profile.to_dict(),
        is_complete=profile.is_required_complete(),
        missing_fields=profile.missing_required_fields(),
    )


@router.put("/profile/{session_id}", response_model=ProfileResponse)
async def update_profile_field(
    session_id: str, req: ProfileUpdateRequest, authorization: str | None = Header(None)
):
    """Update a single profile field."""
    _require_auth(session_id, authorization)
    profile = load_profile(session_id)
    valid_fields = {"province", "score", "subject", "interest", "region", "family", "goal"}
    if req.field not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field: {req.field}")

    # Parse numeric fields
    if req.field == "score":
        try:
            val = int(req.value)
            if not (100 <= val <= 750):
                raise ValueError
            setattr(profile, "score", val)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Score must be integer between 100 and 750")
    else:
        setattr(profile, req.field, req.value)

    save_profile(session_id, profile)
    return ProfileResponse(
        session_id=session_id,
        profile=profile.to_dict(),
        is_complete=profile.is_required_complete(),
        missing_fields=profile.missing_required_fields(),
    )


@router.get("/profile/{session_id}/next-question", response_model=NextQuestionResponse)
async def get_next_question(session_id: str, authorization: str | None = Header(None)):
    """Get the next soul query question for this session."""
    _require_auth(session_id, authorization)
    engine = get_soul_query_engine()
    profile = load_profile(session_id)
    query_state = _load_query_state(session_id)

    question = engine.get_next_question(profile, query_state)
    _save_query_state(session_id, query_state)

    return NextQuestionResponse(
        session_id=session_id,
        question=question,
        round_count=query_state.round_count,
        is_complete=engine.is_query_complete(profile),
    )


@router.post("/profile/{session_id}/skip")
async def skip_field(session_id: str, req: SkipFieldRequest, authorization: str | None = Header(None)):
    """Skip an optional field (uses default value)."""
    _require_auth(session_id, authorization)
    engine = get_soul_query_engine()
    query_state = _load_query_state(session_id)
    engine.handle_skip(query_state, req.field)
    _save_query_state(session_id, query_state)
    return {"status": "skipped", "field": req.field}


# ── Query state persistence (stored in session slots) ─────────────


def _query_state_key(session_id: str) -> str:
    return f"query_state:{session_id}"


def _load_query_state(session_id: str) -> QueryState:
    """Load QueryState from the database."""
    from db.database import get_session
    from db.crud import load_conversation_slots, save_slots

    db = get_session()
    try:
        slot_data = load_conversation_slots(db, session_id) or {}
        qs = slot_data.get("_query_state", {})
        return QueryState(
            round_count=qs.get("round_count", 0),
            asked_fields=qs.get("asked_fields", []),
            skipped_fields=qs.get("skipped_fields", []),
        )
    except Exception:
        return QueryState()
    finally:
        db.close()


def _save_query_state(session_id: str, state: QueryState) -> None:
    """Save QueryState to the database."""
    from db.database import get_session
    from db.crud import get_or_create_conversation, save_slots

    db = get_session()
    try:
        conv = get_or_create_conversation(db, session_id)
        slot_data = {"_query_state": {
            "round_count": state.round_count,
            "asked_fields": state.asked_fields,
            "skipped_fields": state.skipped_fields,
        }}
        save_slots(db, session_id, slot_data)
    except Exception:
        pass
    finally:
        db.close()
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_auth_endpoints.py -v
```

预期：5 passed

- [ ] **Step 6: 运行全量测试确认无回归**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q
```

预期：全部通过

- [ ] **Step 7: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/auth.py server/routes/chat.py server/routes/profile.py tests/test_auth_endpoints.py
git commit -m "feat: add session token auth to profile endpoints and chat SSE"
```

---

### Task 3: 消除双重 LLM 调用

**Files:**
- Modify: `server/graph/graph.py:35-90`
- Modify: `server/graph/nodes/llm_node.py:114-183`
- Modify: `server/routes/chat.py:28-81`
- Create: `tests/test_single_llm_call.py`

**背景：** 当前 Graph 包含 `llm_reason` 节点（生成完整回复），然后 `chat.py:76` 又调用 `llm_node_stream()`（再生成一次）。修复方案：从 Graph 中移除 `llm_reason` 节点，让 Graph 在 `structure_output` 后停止，SSE handler 直接调用 `llm_node_stream` 流式输出。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_single_llm_call.py`:

```python
"""Verify that the graph stops before LLM and SSE handler streams tokens directly."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.graph.graph import build_advisor_graph


def test_graph_does_not_contain_llm_reason_node():
    """The compiled graph should not have an llm_reason node in the complete path."""
    graph = build_advisor_graph()
    # The graph's nodes should not include llm_reason
    node_names = list(graph.get_graph().nodes)
    # llm_reason should be absent from the compiled graph
    assert "llm_reason" not in node_names, (
        f"Graph still contains llm_reason node: {node_names}"
    )


def test_graph_complete_path_ends_at_structure_output():
    """The complete profile path should end at structure_output, not llm_reason."""
    graph = build_advisor_graph()
    # Get the graph representation and check edges
    compiled = graph.get_graph()
    # structure_output should have an edge to render_reply (not to llm_reason)
    edges_from_structure = [
        e for e in compiled.edges
        if e.source == "structure_output"
    ]
    assert len(edges_from_structure) == 1
    assert edges_from_structure[0].target == "render_reply", (
        f"structure_output should connect to render_reply, "
        f"got: {edges_from_structure[0].target}"
    )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_single_llm_call.py -v
```

预期：FAIL — graph 仍包含 llm_reason 节点

- [ ] **Step 3: 修改 graph.py — 移除 llm_reason 节点**

```python
"""LangGraph advisor graph — wires all nodes into a compiled pipeline."""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from server.graph.state import AdvisorState
from server.graph.nodes.security_scan import security_scan_node
from server.graph.nodes.intent import intent_detect_node
from server.graph.nodes.route import scene_route_node
from server.graph.nodes.extract import slot_extract_node
from server.graph.nodes.check import profile_check_node
from server.graph.nodes.question import question_generate_node
from server.graph.nodes.quality_nodes import quality_orchestrate_node
from server.graph.nodes.data_nodes import data_query_node
from server.graph.nodes.rag_node import rag_retrieve_node
from server.graph.nodes.reason import reason_node
from server.graph.nodes.structure import structure_output_node
from server.graph.nodes.render import render_reply_node
from server.graph.nodes.memory import memory_node as memory_update_node


def _profile_has_data(state: AdvisorState) -> str:
    """Routing function: complete profile goes to quality pipeline,
    incomplete profile goes to question generation."""
    if state.get("reply"):
        return "has_reply"
    missing = state.get("missing_fields", [])
    if not missing:
        return "complete"
    return "incomplete"


def build_advisor_graph():
    """Build and compile the advisor StateGraph.

    NOTE: The llm_reason node has been removed from the graph.
    LLM streaming is handled directly by the SSE handler in chat.py
    to avoid double LLM calls. The graph stops at structure_output
    (complete path) or question_generate (incomplete path),
    and the SSE handler streams tokens from llm_node_stream.
    """
    graph = StateGraph(AdvisorState)

    # ── Register nodes (llm_reason removed) ─────────────────────
    graph.add_node("security_scan", security_scan_node)
    graph.add_node("intent_detect", intent_detect_node)
    graph.add_node("scene_route", scene_route_node)
    graph.add_node("slot_extract", slot_extract_node)
    graph.add_node("profile_check", profile_check_node)
    graph.add_node("question_generate", question_generate_node)
    graph.add_node("quality_orchestrate", quality_orchestrate_node)
    graph.add_node("data_query", data_query_node)
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("structure_output", structure_output_node)
    graph.add_node("render_reply", render_reply_node)
    graph.add_node("memory_update", memory_update_node)

    # ── Entry point ───────────────────────────────────────────
    graph.set_entry_point("security_scan")

    # ── Linear chain up to profile_check ──────────────────────
    graph.add_edge("security_scan", "intent_detect")
    graph.add_edge("intent_detect", "scene_route")
    graph.add_edge("scene_route", "slot_extract")
    graph.add_edge("slot_extract", "profile_check")

    # ── Conditional edge from profile_check ───────────────────
    graph.add_conditional_edges(
        "profile_check",
        _profile_has_data,
        {
            "complete": "quality_orchestrate",
            "incomplete": "question_generate",
            "has_reply": "render_reply",
        },
    )

    # ── Question path converges to render → memory → END ───────
    graph.add_edge("question_generate", "render_reply")

    # ── Full pipeline: structure_output → render (no llm_reason) ──
    graph.add_edge("quality_orchestrate", "data_query")
    graph.add_edge("data_query", "rag_retrieve")
    graph.add_edge("rag_retrieve", "reason")
    graph.add_edge("reason", "structure_output")
    # SSE handler calls llm_node_stream directly after graph completes
    graph.add_edge("structure_output", "render_reply")

    # ── Converge: render → memory → END ───────────────────────
    graph.add_edge("render_reply", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


# ── Singleton accessor ────────────────────────────────────────
_advisor_graph = None


def get_advisor_graph():
    """Return the compiled graph (lazy singleton)."""
    global _advisor_graph
    if _advisor_graph is None:
        _advisor_graph = build_advisor_graph()
    return _advisor_graph
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_single_llm_call.py -v
```

预期：2 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/graph/graph.py tests/test_single_llm_call.py
git commit -m "fix: remove llm_reason node from graph to eliminate double LLM call"
```

---

### Task 4: 修复 _maybe_trim logging bug

**Files:**
- Modify: `server/graph/nodes/llm_node.py:208-227`
- Create: `tests/test_maybe_trim.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_maybe_trim.py`:

```python
"""Tests for _maybe_trim logging bug fix (C1/P17)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from server.graph.nodes.llm_node import _maybe_trim


def test_maybe_trim_does_not_crash(caplog):
    """_maybe_trim should not raise TypeError when trimming messages."""
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    # Create more messages than MAX_HISTORY_ROUNDS * 2 (40)
    user_msgs = [{"role": "user", "content": f"Message {i}"} for i in range(50)]
    messages = [system_msg] + user_msgs

    with caplog.at_level(logging.INFO):
        result = _maybe_trim(messages)

    # Should have system + 40 trimmed messages
    assert len(result) == 41  # 1 system + 40 kept
    assert result[0]["role"] == "system"
    # Should NOT have TypeError in logs
    assert "TypeError" not in caplog.text


def test_maybe_trim_no_op_under_limit():
    """_maybe_trim should not modify messages under the limit."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = _maybe_trim(messages)
    assert len(result) == 3
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_maybe_trim.py -v
```

预期：FAIL — `test_maybe_trim_does_not_crash` 触发 TypeError

- [ ] **Step 3: 修复 llm_node.py:223-225**

在 `server/graph/nodes/llm_node.py` 中，将第 223-225 行：

```python
        logger.info(
            dropped, len(rest),
        )
```

替换为：

```python
        logger.info(
            "Context trimmed: dropped %d messages, keeping %d", dropped, len(rest),
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_maybe_trim.py -v
```

预期：2 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/graph/nodes/llm_node.py tests/test_maybe_trim.py
git commit -m "fix: correct logging format string in _maybe_trim (was crashing on trim)"
```

---

### Task 5: 前端 XSS 修复 — DOMPurify 净化

**Files:**
- Create: `frontend/src/utils/sanitize.js`
- Modify: `frontend/src/components/chat/MessageBubble.vue`
- Modify: `frontend/package.json` (添加 dompurify 依赖)

- [ ] **Step 1: 安装 DOMPurify**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor/frontend && npm install dompurify
```

- [ ] **Step 2: 创建 sanitize 工具**

创建 `frontend/src/utils/sanitize.js`:

```javascript
/**
 * HTML sanitization utility — wraps DOMPurify to safely render
 * AI-generated markdown content without XSS vectors.
 */
import DOMPurify from 'dompurify'

/**
 * Sanitize HTML string, stripping all dangerous elements while
 * keeping safe formatting tags.
 * @param {string} html - Raw HTML string (e.g., from markdown conversion)
 * @returns {string} Sanitized HTML safe for v-html rendering
 */
export function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['strong', 'em', 'br', 'p', 'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
  })
}

/**
 * Convert simple markdown to HTML and sanitize.
 * Handles: **bold**, newlines → <br>
 * @param {string} text - Raw text with markdown
 * @returns {string} Sanitized HTML
 */
export function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  return sanitizeHtml(html)
}
```

- [ ] **Step 3: 修改 MessageBubble.vue**

将 `frontend/src/components/chat/MessageBubble.vue` 的完整内容替换为：

```vue
<template>
  <div :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
    <div :class="['max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
      message.role === 'user' ? 'bg-blue-600 text-white rounded-br-sm' : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm']">
      <div v-html="renderedContent" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../../utils/sanitize'
const props = defineProps({ message: Object })
const renderedContent = computed(() => {
  return renderMarkdown(props.message.content || '')
})
</script>
```

- [ ] **Step 4: 验证构建**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor/frontend && npm run build
```

预期：构建成功，无错误

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add frontend/package.json frontend/package-lock.json frontend/src/utils/sanitize.js frontend/src/components/chat/MessageBubble.vue
git commit -m "fix: sanitize AI output with DOMPurify to prevent stored XSS via v-html"
```

---

### Task 6: Nginx 安全响应头

**Files:**
- Modify: `nginx.conf`

- [ ] **Step 1: 修改 nginx.conf**

将 `nginx.conf` 替换为：

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api_backend {
        server api:8000;
    }

    upstream frontend_backend {
        server frontend:80;
    }

    # ── Security headers (applied to all responses) ──────────
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;" always;

    server {
        listen 80;

        location /api/ {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
        }

        location /ws/ {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 3600s;
            proxy_buffering off;
        }

        location / {
            proxy_pass http://frontend_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

- [ ] **Step 2: 验证 nginx 配置语法**

```bash
docker run --rm -v /home/dev/projects/gaobao/gaobao-advisor/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t
```

预期：`syntax is ok` / `test is successful`

- [ ] **Step 3: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add nginx.conf
git commit -m "security: add CSP, X-Frame-Options, X-Content-Type-Options headers to nginx"
```

---

### Task 7: pytest-cov + CI 覆盖率门禁

**Files:**
- Modify: `pyproject.toml:37-43`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 修改 pyproject.toml**

将 `pyproject.toml` 的 `[tool.pytest.ini_options]` 部分修改为：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--tb=short",
    "-v",
    "--cov=server",
    "--cov=quality",
    "--cov=analytics",
    "--cov=slots",
    "--cov=config",
    "--cov=db",
    "--cov-report=term-missing",
    "--cov-fail-under=70",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests requiring external services",
]
```

- [ ] **Step 2: 修改 CI 配置**

将 `.github/workflows/ci.yml` 的 test job 修改为：

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Run ruff check
        run: ruff check .

      - name: Run ruff format check
        run: ruff format --check .

  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Run tests with coverage
        run: python -m pytest tests/ -v --tb=short --cov-fail-under=70

      - name: Upload coverage report
        if: matrix.python-version == '3.11'
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/
          retention-days: 7
```

- [ ] **Step 3: 本地验证覆盖率**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && pip install -e ".[dev]" && python -m pytest tests/ --cov=server --cov=quality --cov=analytics --cov=slots --cov=config --cov=db --cov-report=term-missing --cov-fail-under=70 -q
```

预期：覆盖率 ≥ 70% 或显示具体未覆盖行

- [ ] **Step 4: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add pyproject.toml .github/workflows/ci.yml
git commit -m "ci: add pytest-cov coverage measurement with 70% fail-under threshold"
```

---

### Task 8: 创建 CONVENTIONS.md

**Files:**
- Create: `CONVENTIONS.md`

- [ ] **Step 1: 创建文件**

创建 `CONVENTIONS.md`:

```markdown
# Gaobao Advisor — 工程约束 (CONVENTIONS)

> 本文件是项目的工程规范。所有贡献者（包括 AI 工具）必须遵守。

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| Backend | Python / FastAPI / LangGraph | 3.10+ / 0.100+ / latest |
| ORM | SQLAlchemy | 2.x |
| Database | SQLite (WAL mode) | — |
| Frontend | Vue 3 / Vite / Tailwind CSS | 3.5+ / 8+ / 4+ |
| Testing | pytest / ruff | 7+ / 0.4+ |
| CI | GitHub Actions | — |
| Deploy | Docker / Nginx | — |

## 目录结构

```
server/          → FastAPI 后端（routes/graph/services/middleware）
db/              → SQLAlchemy ORM 层（models/crud/database）
quality/         → 质量控制模块（emotion/risk/validator）
slots/           → 槽位提取（extractor/patterns）
config/          → 配置加载（loader + YAML）
tests/           → 所有测试文件（pytest 发现路径）
frontend/        → Vue 3 SPA
prompts/         → 系统提示词版本管理
knowledge/       → RAG 知识库（groups/quotes）
scripts/         → 数据导入/工具脚本
```

## 编码标准

- **文件大小**：≤ 800 行（超限需拆分）
- **函数大小**：≤ 50 行
- **嵌套层级**：≤ 4 层（使用 early return）
- **类型标注**：所有函数签名必须有类型标注
- **格式化**：`ruff format .`（line-length=120）
- **Lint**：`ruff check .`（0 errors）

## 测试要求

- **覆盖率**：≥ 70%（`--cov-fail-under=70`）
- **测试模式**：AAA（Arrange-Act-Assert）
- **LLM Mock**：所有涉及 LLM 调用的测试必须 mock
- **E2E**：核心对话流程至少 5 条 E2E 路径
- **运行**：`python -m pytest tests/ -v`

## 安全红线

- ❌ 禁止硬编码密钥（使用环境变量）
- ❌ 禁止 `v-html` 直接渲染未净化内容（使用 DOMPurify）
- ✅ 所有用户输入经过 `sanitize_input()` 处理
- ✅ 所有 DB 查询使用 SQLAlchemy ORM（参数化）
- ✅ Profile 端点必须验证 session token
- ✅ SSRF 防御覆盖所有 URL 检查点

## Git 规范

- Commit 格式：`<type>: <description>`
- 类型：feat / fix / refactor / docs / test / chore / perf / ci
- 分支：main（生产）、feature/*（开发）

## 禁止行为

- ❌ 不写 `except Exception: pass`（必须 logging）
- ❌ 不用 `global` 声明非单例变量
- ❌ 不在测试文件外放测试代码
- ❌ 不提交 `.env` / `secrets.toml`
- ❌ 不跳过 CI 流水线
```

- [ ] **Step 2: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add CONVENTIONS.md
git commit -m "docs: add CONVENTIONS.md engineering constraints"
```

---

## Phase A 完成检查点

```bash
# 运行全量测试
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q

# 检查 lint
ruff check server/ tests/ --count

# 验证覆盖率
python -m pytest tests/ --cov=server --cov=quality --cov-report=term-missing -q
```

**Phase A 完成标准：**
- [ ] 621+ tests passed
- [ ] Session token 签发和验证工作正常
- [ ] Profile 端点需要 Bearer token
- [ ] Graph 不再包含 llm_reason 节点
- [ ] `_maybe_trim` 不再崩溃
- [ ] DOMPurify 净化 AI 输出
- [ ] Nginx 返回安全响应头
- [ ] CI 中有覆盖率报告
- [ ] CONVENTIONS.md 存在

---

## Phase B — P1 高优项修复

---

### Task 9: 修复 N+1 查询

**Files:**
- Modify: `db/crud.py:165-189`

- [ ] **Step 1: 写失败测试**

在 `tests/` 中创建或追加 N+1 测试（示例）：

```python
"""Test that query_admission_from_db uses eager loading (no N+1)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from db.crud import query_admission_from_db


def test_query_admission_from_db_no_individual_major_queries():
    """query_admission_from_db should not query Major individually per score."""
    mock_db = MagicMock()
    mock_school = MagicMock()
    mock_school.name = "测试大学"
    mock_school.level = "985"
    mock_school.id = 1

    mock_score = MagicMock()
    mock_score.major_id = 10
    mock_score.province = "北京"
    mock_score.year = 2024
    mock_score.batch = "本科一批"
    mock_score.subject_type = "物理类"
    mock_score.min_score = 650
    mock_score.avg_score = 660
    mock_score.min_rank = 1000

    # After fix, this should use joinedload — the query should include
    # a .options() call or the Major should be accessed via relationship
    mock_db.query.return_value.filter.return_value.first.return_value = mock_school
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_score]

    # Access major via relationship instead of separate query
    mock_score.major = MagicMock()
    mock_score.major.name = "计算机科学"

    result = query_admission_from_db(mock_db, "测试大学", "北京")
    assert len(result) == 1
    assert result[0]["major"] == "计算机科学"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_n_plus_one.py -v
```

- [ ] **Step 3: 修改 crud.py — 使用 relationship 或批量加载**

在 `db/models.py` 的 `AdmissionScore` 模型中添加 relationship（如果不存在）：

```python
# 在 AdmissionScore 类中添加：
major = relationship("Major", primaryjoin="AdmissionScore.major_id == Major.id", foreign_keys="AdmissionScore.major_id", viewonly=True)
```

然后修改 `db/crud.py` 的 `query_admission_from_db` 函数，将第 175 行的 N+1 查询：

```python
        major = db.query(Major).filter(Major.id == s.major_id).first() if s.major_id else None
```

替换为使用 relationship：

```python
        major = s.major if s.major_id else None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_n_plus_one.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add db/crud.py db/models.py tests/test_n_plus_one.py
git commit -m "fix: eliminate N+1 queries in query_admission_from_db via relationship"
```

---

### Task 10: 速率限制器 TTL 驱逐

**Files:**
- Modify: `server/middleware/ratelimit.py`
- Create: `tests/test_ratelimit_eviction.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ratelimit_eviction.py`:

```python
"""Tests for rate limiter TTL eviction mechanism."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from unittest.mock import patch
from server.middleware.ratelimit import TokenBucketLimiter


def test_evicts_idle_entries():
    """Entries idle for > max_idle seconds should be evicted."""
    limiter = TokenBucketLimiter(rate=20, capacity=40)

    # Fill some buckets
    for i in range(5):
        limiter.allow(f"10.0.0.{i}")

    assert len(limiter._buckets) == 5

    # Simulate time passing (1 hour = 3600s)
    with patch("time.monotonic", return_value=time.monotonic() + 3601):
        # Trigger eviction by calling allow with a new IP
        limiter.allow("10.0.0.99")

    # Old entries should be evicted (idle > 1 hour)
    # Only the new entry should remain (plus maybe one refreshed)
    assert len(limiter._buckets) < 5


def test_active_entries_not_evicted():
    """Entries that were recently accessed should NOT be evicted."""
    limiter = TokenBucketLimiter(rate=20, capacity=40)

    # Access all entries recently
    for i in range(5):
        limiter.allow(f"10.0.0.{i}")

    # Small time passage (10 seconds)
    with patch("time.monotonic", return_value=time.monotonic() + 10):
        limiter.allow("10.0.0.99")

    # All entries should still exist (10s < 3600s idle threshold)
    assert len(limiter._buckets) >= 5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_ratelimit_eviction.py -v
```

预期：FAIL — 无驱逐逻辑

- [ ] **Step 3: 修改 ratelimit.py — 添加 TTL 驱逐**

```python
"""Token bucket rate limiter for FastAPI with TTL eviction."""
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Evict entries idle longer than this (seconds)
_MAX_IDLE_SECONDS = 3600  # 1 hour
# Run eviction check every N requests
_EVICTION_INTERVAL = 500


class TokenBucketLimiter:
    """Per-IP token bucket rate limiter with TTL-based eviction."""

    def __init__(self, rate: float = 20, capacity: int = 40):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}
        self._request_count: int = 0

    def allow(self, ip: str) -> bool:
        now = time.monotonic()

        # Periodic eviction of idle entries
        self._request_count += 1
        if self._request_count % _EVICTION_INTERVAL == 0:
            self._evict_idle(now)

        if ip not in self._buckets:
            self._buckets[ip] = (self.capacity, now)
        tokens, last = self._buckets[ip]
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.rate)
        if tokens < 1:
            return False
        self._buckets[ip] = (tokens - 1, now)
        return True

    def _evict_idle(self, now: float) -> None:
        """Remove entries that have been idle (fully refilled) for too long."""
        idle_ips = [
            ip for ip, (tokens, last) in self._buckets.items()
            if now - last > _MAX_IDLE_SECONDS and tokens >= self.capacity
        ]
        for ip in idle_ips:
            del self._buckets[ip]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware enforcing token bucket rate limits per IP."""

    def __init__(self, app, rate: float = 20, capacity: int = 40):
        super().__init__(app)
        self.limiter = TokenBucketLimiter(rate=rate, capacity=capacity)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not self.limiter.allow(client_ip):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        return await call_next(request)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_ratelimit_eviction.py -v
```

预期：2 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/middleware/ratelimit.py tests/test_ratelimit_eviction.py
git commit -m "fix: add TTL eviction to rate limiter to prevent memory leak"
```

---

### Task 11: SQLite WAL 模式

**Files:**
- Modify: `db/database.py:30-40`

- [ ] **Step 1: 写测试**

在现有测试文件中追加，或创建 `tests/test_wal_mode.py`:

```python
"""Test that SQLite uses WAL journal mode."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.database import engine


def test_sqlite_wal_mode_enabled():
    """SQLite should be in WAL journal mode for better concurrency."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
    assert mode.lower() == "wal", f"Expected WAL mode, got: {mode}"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_wal_mode.py -v
```

预期：FAIL — 当前是 DELETE 模式

- [ ] **Step 3: 修改 database.py — 启用 WAL**

在 `db/database.py` 的 `engine = create_engine(...)` 之后添加 WAL 启用：

```python
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode for better concurrent read/write performance
def _set_wal_mode(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

from sqlalchemy import event
event.listen(engine, "connect", _set_wal_mode)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_wal_mode.py -v
```

预期：1 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add db/database.py tests/test_wal_mode.py
git commit -m "perf: enable SQLite WAL mode for improved concurrent access"
```

---

### Task 12: 合并重复安全逻辑

**Files:**
- Modify: `utils.py`
- Modify: `server/middleware/security.py`
- Modify: `tests/test_auth.py` (追加 SSRF 测试)

- [ ] **Step 1: 写测试**

在 `tests/test_auth.py` 中追加：

```python
from utils import is_safe_url


class TestSSRF:
    def test_blocks_localhost(self):
        assert is_safe_url("http://localhost:8080/admin") is False

    def test_blocks_private_ip(self):
        assert is_safe_url("http://192.168.1.1/secret") is False

    def test_blocks_metadata(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data") is False

    def test_allows_public_url(self):
        assert is_safe_url("https://www.example.com") is True

    def test_blocks_hex_encoded_loopback(self):
        assert is_safe_url("http://0x7f000001/secret") is False
```

- [ ] **Step 2: 运行测试确认通过（如果 utils.py 已有实现）或确认失败**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_auth.py::TestSSRF -v
```

- [ ] **Step 3: 统一安全函数到 utils.py**

确保 `utils.py` 包含统一的 `is_safe_url` 和 `check_ssrf` 函数（如果尚不存在，从 `server/middleware/security.py` 迁移并增强）。然后修改 `server/middleware/security.py` 导入 `utils` 中的函数：

```python
# 在 server/middleware/security.py 顶部添加：
from utils import is_safe_url

# 删除 server/middleware/security.py 中的 _BLOCKED_HOSTS, _PRIVATE_RANGES,
# _parse_ip, check_ssrf 函数（已迁移到 utils.py）
```

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add utils.py server/middleware/security.py tests/test_auth.py
git commit -m "refactor: consolidate SSRF/injection detection into utils.py (single source)"
```

---

### Task 13: 修复 Silent Exception Swallowing

**Files:**
- Modify: `server/graph/nodes/rag_node.py:39-41`
- Modify: `server/routes/profile.py:131,151`

- [ ] **Step 1: 修改 rag_node.py**

找到 `server/graph/nodes/rag_node.py` 中的 `except Exception: pass` 块，替换为：

```python
    except Exception:
        logger.debug("RAG retrieval failed, proceeding without RAG context", exc_info=True)
```

如果文件顶部没有 `import logging` 和 `logger = logging.getLogger(__name__)`，添加它们。

- [ ] **Step 2: 修改 profile.py:131,151**

找到 `server/routes/profile.py` 中 `_load_query_state` 和 `_save_query_state` 的 `except Exception` 块：

```python
# _load_query_state 中（约第 131 行）：
    except Exception:
        return QueryState()

# 替换为：
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Failed to load query state: %s", exc)
        return QueryState()
```

```python
# _save_query_state 中（约第 151 行）：
    except Exception:
        pass

# 替换为：
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to save query state: %s", exc)
```

- [ ] **Step 3: 运行测试确认无回归**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q
```

- [ ] **Step 4: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add server/graph/nodes/rag_node.py server/routes/profile.py
git commit -m "fix: add logging to silent except blocks in rag_node and profile"
```

---

### Task 14: ruff 全量格式化 + Lint 修复

**Files:**
- 多个 `*.py` 文件（自动修复）

- [ ] **Step 1: 自动修复可修复的 lint 错误**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && ruff check . --fix
```

- [ ] **Step 2: 全量格式化**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && ruff format .
```

- [ ] **Step 3: 检查剩余错误**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && ruff check . --count
```

预期：0 errors 或仅剩无法自动修复的错误

- [ ] **Step 4: 运行测试确认格式化未破坏任何东西**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add -A
git commit -m "chore: ruff check --fix + ruff format across codebase"
```

---

### Task 15: 移动错位测试文件

**Files:**
- Move: `analytics/test_tracker.py` → `tests/test_tracker.py`
- Move: `quality/test_quality.py` → `tests/test_quality.py`

- [ ] **Step 1: 移动文件**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
mv analytics/test_tracker.py tests/test_tracker.py
mv quality/test_quality.py tests/test_quality.py
```

- [ ] **Step 2: 修复导入路径**

检查移动后的文件中的 `sys.path.insert` 和 import 语句，确保它们引用正确的模块路径。通常需要将 `from .. import` 改为绝对导入。

- [ ] **Step 3: 运行被移动的测试确认通过**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_tracker.py tests/test_quality.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add tests/test_tracker.py tests/test_quality.py
git commit -m "fix: move misplaced test files from source packages to tests/"
```

---

### Task 16: 前端基础 Vitest 配置

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/utils/__tests__/sanitize.test.js`

- [ ] **Step 1: 安装 Vitest**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor/frontend && npm install -D vitest @vue/test-utils jsdom
```

- [ ] **Step 2: 添加 test 脚本到 package.json**

在 `frontend/package.json` 的 `scripts` 中添加：

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: 创建 Vitest 配置**

创建 `frontend/vitest.config.js`:

```javascript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

- [ ] **Step 4: 写 sanitize 工具测试**

创建 `frontend/src/utils/__tests__/sanitize.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { sanitizeHtml, renderMarkdown } from '../sanitize'

describe('sanitizeHtml', () => {
  it('strips script tags', () => {
    const result = sanitizeHtml('<script>alert("xss")</script>Hello')
    expect(result).not.toContain('<script>')
    expect(result).toContain('Hello')
  })

  it('strips event handlers', () => {
    const result = sanitizeHtml('<img src=x onerror="alert(1)">')
    expect(result).not.toContain('onerror')
  })

  it('preserves safe tags', () => {
    const result = sanitizeHtml('<strong>bold</strong> and <em>italic</em>')
    expect(result).toContain('<strong>')
    expect(result).toContain('<em>')
  })
})

describe('renderMarkdown', () => {
  it('converts bold markdown', () => {
    const result = renderMarkdown('**hello**')
    expect(result).toContain('<strong>hello</strong>')
  })

  it('converts newlines to br', () => {
    const result = renderMarkdown('line1\nline2')
    expect(result).toContain('<br>')
  })

  it('escapes HTML in input', () => {
    const result = renderMarkdown('<script>alert(1)</script>')
    expect(result).not.toContain('<script>')
  })

  it('handles empty input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
  })
})
```

- [ ] **Step 5: 运行前端测试**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor/frontend && npx vitest run
```

预期：7 tests passed

- [ ] **Step 6: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/utils/__tests__/
git commit -m "test: add Vitest with sanitize utility tests for frontend XSS prevention"
```

---

### Task 17: 修复前端 index.html

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 修改 index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="高考志愿AI顾问 — 基于RAG的智能志愿填报助手，支持高考志愿、考研规划、职业方向指导" />
    <title>高报AI顾问 — 高考志愿/考研/职业规划</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 2: 验证构建**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add frontend/index.html
git commit -m "fix: set correct lang=zh-CN, title, and meta description in index.html"
```

---

## Phase B 完成检查点

```bash
# 全量测试
cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/ -x --tb=short -q

# 前端测试
cd frontend && npx vitest run

# Lint
cd .. && ruff check . --count

# 格式化
ruff format --check .
```

**Phase B 完成标准：**
- [ ] N+1 查询已修复（1 次 DB 调用）
- [ ] 速率限制器有 TTL 驱逐
- [ ] SSRF/injection 逻辑已统一
- [ ] SQLite WAL 模式已启用
- [ ] 前端 Vitest 配置就绪 + 基础测试通过
- [ ] Silent exception 已修复
- [ ] ruff 0 errors + 格式化通过
- [ ] 错位测试文件已移动
- [ ] index.html lang/title/description 已修正

---

## 自审清单

1. **Spec 覆盖**：审计报告中 6 个交叉命中问题 → Task 1-2 (X-1), Task 5 (X-2), Task 3 (X-3), Task 10 (X-4), Task 12 (X-5), Task 7+16 (X-6) ✅
2. **22 项自查表**：P0 全部覆盖 (Task 1-8), P1 全部覆盖 (Task 9-17) ✅
3. **占位符扫描**：所有步骤包含实际代码和文件路径，无 TBD/TODO ✅
4. **类型一致性**：`create_session_token` / `verify_session_token` 在 auth.py 定义，chat.py 和 profile.py 引用一致 ✅
