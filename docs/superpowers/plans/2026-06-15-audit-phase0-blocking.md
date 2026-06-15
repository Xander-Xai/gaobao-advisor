# Phase 0 — 阻断性修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 P0 issues that can cause production outages: LLM timeout, SSE crash on graph failure, and session secret cross-process mismatch.

**Architecture:** Three independent, localized fixes — no cross-file dependencies. Each can be verified in isolation. Total estimated time: ~15 minutes.

**Tech Stack:** Python 3.11+, FastAPI, OpenAI SDK, HMAC auth

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `server/graph/nodes/llm_node.py:64-67` | Add timeout to OpenAI() constructor |
| Test | `tests/server/graph/test_llm_node.py` | Add timeout default test |
| Modify | `server/routes/chat.py:55-56` | Wrap Phase 1 in try-except |
| Modify | `server/auth.py:15-23` | Add logging for auto-generated secret |
| Modify | `.env.example:52` | Add SESSION_SECRET entry |

---

### Task 1: Add timeout to LLM client

**Files:**
- Modify: `server/graph/nodes/llm_node.py:64-67`

- [ ] **Step 1: Modify `_get_llm_client` to accept timeout from config**

Change lines 64-67 from:
```python
_client = OpenAI(
    api_key=api_key,
    base_url=cfg["base_url"],
)
```
to:
```python
_client = OpenAI(
    api_key=api_key,
    base_url=cfg["base_url"],
    timeout=cfg.get("timeout", 120.0),
    max_retries=2,
)
```

Rationale: `timeout=120.0` limits per-request wait to 2 minutes (vs SDK default 10 min). `max_retries=2` handles transient failures at the client level before our `_sync_retry` kicks in. Both values are configurable via `llm_providers.yaml`.

- [ ] **Step 2: Verify the change**

Run: `python3 -c "from server.graph.nodes.llm_node import _get_llm_client; print('import OK')"`
Expected: No error (client won't be instantiated without API key).

Run: `ruff check server/graph/nodes/llm_node.py`
Expected: 0 errors

- [ ] **Step 3: Run existing tests**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python3 -m pytest tests/server/graph/test_llm_node.py -v 2>&1 | tail -20`
Expected: tests pass (existing tests should not be affected by timeout addition)

- [ ] **Step 4: Commit**

```bash
git add server/graph/nodes/llm_node.py
git commit -m "fix: add explicit timeout and max_retries to OpenAI client (P0-audit)"
```

---

### Task 2: Add try-except around graph.invoke in SSE generator

**Files:**
- Modify: `server/routes/chat.py:53-56`

- [ ] **Step 1: Add try-except around Phase 1 graph.invoke**

Change lines 55-56 from:
```python
# Phase 1: Run graph (synchronous, offloaded to thread)
result = await asyncio.to_thread(graph.invoke, initial_state)
```
to:
```python
# Phase 1: Run graph (synchronous, offloaded to thread)
try:
    result = await asyncio.to_thread(graph.invoke, initial_state)
except Exception as e:
    logger = __import__("logging").getLogger(__name__)
    logger.exception("Phase 1 graph.invoke failed for session %s", session_id)
    yield f"data: {json.dumps({'type': 'error', 'code': 'GRAPH_FAILED', 'message': '服务暂时不可用，请稍后重试'})}\n\n"
    return
```

Note: `logger` is obtained inline to avoid adding a new module-level import. If `server/routes/chat.py` already has a logger at the top (check line 1-10), use that instead.

- [ ] **Step 2: Verify the change**

Read the top of `server/routes/chat.py` to check for existing logger, and if present, use it instead of inline logger.

Run: `ruff check server/routes/chat.py`
Expected: 0 errors

- [ ] **Step 3: Run chat SSE test**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python3 -m pytest tests/test_chat_sse.py -v 2>&1 | tail -20`
Expected: tests pass

- [ ] **Step 4: Commit**

```bash
git add server/routes/chat.py
git commit -m "fix: wrap Phase 1 graph.invoke in try-except for graceful SSE error (P0-audit)"
```

---

### Task 3: Fix auth.py cross-process secret and .env.example

**Files:**
- Modify: `server/auth.py:15-23`
- Modify: `.env.example:52`

- [ ] **Step 1: Add module-level logger and startup warning to auth.py**

Add after line 13 (`import secrets`):
```python
import logging
logger = logging.getLogger(__name__)
```

Change lines 15-23 from:
```python
_SECRET = os.getenv("SESSION_SECRET", "")


def _get_secret() -> bytes:
    """Return the HMAC signing secret, generating one if not configured."""
    global _SECRET
    if not _SECRET:
        _SECRET = secrets.token_hex(32)
    return _SECRET.encode()
```
to:
```python
_SECRET = os.getenv("SESSION_SECRET", "")


def _get_secret() -> bytes:
    """Return the HMAC signing secret, generating one if not configured."""
    global _SECRET
    if not _SECRET:
        _SECRET = secrets.token_hex(32)
        logger.warning(
            "SESSION_SECRET not set — using ephemeral random secret. "
            "Session tokens will be invalidated on restart. "
            "Set SESSION_SECRET in .env for production."
        )
    return _SECRET.encode()
```

- [ ] **Step 2: Add SESSION_SECRET to .env.example**

Append to end of `.env.example`:
```env
# ── Session 签名密钥（生产环境必填） ──
# 生成命令：python3 -c "import secrets; print(secrets.token_hex(32))"
# 不填则每次重启随机生成，多 worker 下 session token 失效
SESSION_SECRET=
```

- [ ] **Step 3: Verify changes**

Run: `python3 -c "from server.auth import create_session_token, verify_session_token; t = create_session_token('test'); assert verify_session_token('test', t); print('auth OK')"`
Expected: `auth OK` (and a warning log about missing SESSION_SECRET)

Run: `ruff check server/auth.py`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add server/auth.py .env.example
git commit -m "fix: add SESSION_SECRET warning and .env.example entry for cross-process safety (P0-audit)"
```

---

## Phase 0 Verification (all tasks complete)

- [ ] Run final check: `ruff check server/graph/nodes/llm_node.py server/routes/chat.py server/auth.py`
      Expected: 0 errors

- [ ] Run: `python3 -m pytest tests/test_chat_sse.py tests/server/graph/test_llm_node.py tests/test_auth.py -v 2>&1 | tail -30`
      Expected: all tests pass (0 failed)

- [ ] Run: `python3 -c "from server.auth import create_session_token, verify_session_token; t = create_session_token('x'); assert verify_session_token('x', t); print('✅ Phase 0 auth validated')"`
      Expected: ✅ message
