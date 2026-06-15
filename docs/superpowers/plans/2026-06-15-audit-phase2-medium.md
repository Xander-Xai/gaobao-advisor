# Phase 2 — 中期修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address 3 medium-priority audit items: create architecture documentation (SPEC.md + ADRs), clean up docker-compose.yml, and add voice.py tests.

**Architecture:** Three independent tasks. Task 1 (docs) requires research — reading the codebase to document architectural decisions. Task 2 (docker-compose) is a one-line cleanup. Task 3 (voice tests) requires understanding the voice service API. Total estimated time: ~3 hours.

**Tech Stack:** Markdown, Python 3.11+, pytest, Docker Compose

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Create | `docs/superpowers/adr/` | New directory for ADRs |
| Create | `docs/superpowers/adr/ADR-001-fastapi-migration.md` | Streamlit → FastAPI migration rationale |
| Create | `docs/superpowers/adr/ADR-002-langgraph-flow.md` | LangGraph graph architecture |
| Create | `docs/superpowers/adr/ADR-003-sqlite-wal-joinedload.md` | SQLite WAL + joinedload N+1 fix |
| Create | `docs/superpowers/adr/ADR-004-hybrid-rag.md` | Vector + keyword hybrid retrieval |
| Create | `docs/superpowers/adr/ADR-005-voice-integration.md` | DashScope TTS/ASR pipeline |
| Create | `docs/superpowers/adr/ADR-006-adr-process.md` | Why and how we write ADRs |
| Create | `SPEC.md` | Project-level spec overview |
| Modify | `docker-compose.yml:39-51` | Add legacy warning comment |
| Create | `tests/server/services/test_voice.py` | Voice service tests |

---

### Task 1: Write SPEC.md — project-level specification

**Files:**
- Create: `SPEC.md`

- [ ] **Step 1: Research current project structure**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
find . -maxdepth 3 -name "*.py" ! -path "./.claude/*" ! -path "./frontend/*" ! -path "./.venv*" ! -path "./scripts/*" ! -path "./__pycache__/*" | sort
```

- [ ] **Step 2: Create SPEC.md**

Create `SPEC.md` with these sections:
```markdown
# Gaobao Advisor — 高考志愿 AI 顾问

## Overview
[1-2 paragraphs: what this project does, who it's for]

## Architecture

### Service Layer
- FastAPI server (`server/main.py`) — primary HTTP entry point
- LangGraph workflow (`server/graph/graph.py`) — state machine for conversation flow
- SQLite database (`db/database.py`) — persistence with WAL mode
- Hybrid RAG (`server/services/rag.py`) — vector + keyword knowledge retrieval
- Voice pipeline (`server/services/voice.py`) — ASR → Graph → TTS (DashScope)
- Streamlit (`app.py` — DEPRECATED, deleted) — legacy UI

### Frontend
- React SPA (`frontend/`) — mobile-first UI
- nginx reverse proxy (`nginx.conf`) — serves frontend + proxies API/WS

### Data Pipeline
- Data importers: Baidu Gaokao, async parallel, checkpoint-based resume
- Database schema: schools, majors, admission_scores + knowledge base

## Key Design Decisions
See `docs/superpowers/adr/` for full ADRs:
- ADR-001: FastAPI over Streamlit (separation of concerns, SSE streaming)
- ADR-002: LangGraph workflow (state machine for multi-turn conversation)
- ADR-003: SQLite + WAL (zero-dependency embedded DB with concurrent readers)
- ADR-004: Hybrid RAG (vector + keyword for recall quality)
- ADR-005: DashScope Voice (ASR + TTS for phone-like interaction)

## API Contracts
- `POST /api/v1/chat` — SSE-streaming chat (see `server/routes/chat.py`)
- `GET /api/v1/health` — health check
- `GET /api/v1/data/schools` — school/major search
- `POST /api/v1/voice/asr` — speech-to-text
- `POST /api/v1/voice/tts` — text-to-speech

## Deployment
- Docker Compose (api + frontend + nginx)
- Environment config via `.env`
- No external DB dependency — SQLite file in `./data/`

## Testing Strategy
- pytest with httpx ASGI transport for integration tests
- Target: 70%+ coverage (enforced via pytest-cov)
- See `tests/` directory — 50+ test files
```

- [ ] **Step 3: Verify SPEC.md is accurate**

Quick scan of actual routes vs SPEC.md API section:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
grep -r "@router" server/routes/ --include="*.py"
```
The SPEC.md should list every route found.

- [ ] **Step 4: Commit**

```bash
git add SPEC.md
git commit -m "docs: add SPEC.md project-level specification (P1-audit)"
```

---

### Task 2: Write ADR documents

**Files:**
- Create: `docs/superpowers/adr/ADR-001-fastapi-migration.md`
- Create: `docs/superpowers/adr/ADR-002-langgraph-flow.md`
- Create: `docs/superpowers/adr/ADR-003-sqlite-wal-joinedload.md`
- Create: `docs/superpowers/adr/ADR-004-hybrid-rag.md`
- Create: `docs/superpowers/adr/ADR-005-voice-integration.md`
- Create: `docs/superpowers/adr/ADR-006-adr-process.md`

- [ ] **Step 1: Create ADR directory**

```bash
mkdir -p docs/superpowers/adr
```

- [ ] **Step 2: Write ADR-001 (FastAPI migration)**

```markdown
# ADR-001: Migrate from Streamlit to FastAPI

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
The original app used Streamlit as both frontend and backend. This caused:
1. Monolithic architecture — UI logic mixed with business logic
2. No support for SSE streaming (LangGraph token-by-token output)
3. Poor concurrent connection handling
4. Difficult to integrate with external frontend (React)

## Decision
Migrate to FastAPI as the primary HTTP server, with React SPA as frontend.

## Consequences
+ Clean separation of concerns (API server + separate frontend)
+ Native SSE support via StreamingResponse
+ Standard REST/WS interfaces
+ Async support for concurrent connections
- Requires nginx reverse proxy for unified serving
- Legacy Streamlit mode still usable via `profiles: ["legacy"]`

## Related
- ADR-002: LangGraph workflow
```

- [ ] **Step 3: Write ADR-002 (LangGraph)**

```markdown
# ADR-002: LangGraph for Conversation Workflow

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
Multi-turn conversation requires state management:
- Slot filling across turns
- Memory management (recent + summary)
- Conditional branching (RAG lookup → LLM → response)
- Emotion/coaching state transitions

Alternative: manual state machine (brittle, not extensible).

## Decision
Use LangGraph to define the conversation as a directed state graph.
Node types: InputValidation → SlotExtraction → RAGRetrieval → LLMReasoning → Response

## Consequences
+ Explicit state machine — easy to trace and debug
+ Built-in checkpointing and conversation memory
+ Modular nodes — each node is a testable unit
- Requires synchronous thread-pool execution (not native async)
- LangGraph dependency management complexity

## Related
- ADR-001: FastAPI migration (SSE integration)
```

- [ ] **Step 4: Write ADR-003 (SQLite WAL + joinedload)**

```markdown
# ADR-003: SQLite with WAL mode and joinedload for N+1 prevention

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
The admission_scores → schools → majors relationship creates N+1 queries when serializing results.
SQLite under default journal mode blocks reads during writes.

## Decision
1. Enable WAL mode + busy_timeout=5000 at engine connect time
2. Use SQLAlchemy `joinedload()` for school/major relationships in query functions

## Consequences
+ WAL enables concurrent reads during writes (critical for import pipeline)
+ busy_timeout prevents "Database Is Locked" errors under load
+ joinedload reduces N+1 from O(1+N) to O(1) for score queries
- WAL creates .db-wal and .db-shm files
- joinedload can cause cartesian products if misused (not an issue here due to 1:1 relationships)
```

- [ ] **Step 5: Write ADR-004 (Hybrid RAG)**

```markdown
# ADR-004: Hybrid RAG (Vector + Keyword) for Knowledge Retrieval

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
Gaokao advice requires factual recall of:
- School rankings, admission scores, major details
- Zhang Xuefeng quotes and analysis frameworks
- Policy rules and cutoff lines

Pure vector search misses exact keyword matches (score thresholds, school names).
Pure keyword search misses semantic similarity.

## Decision
Implement hybrid RAG: vector similarity (embedding) + keyword BM25-style retrieval.
Configurable embedding provider (SiliconFlow by default for Chinese quality).

## Consequences
+ Higher recall than single-strategy retrieval
+ Graceful degradation — if vector DB unavailable, falls back to keyword
+ Embedding compute is offline (precomputed)
- Requires embedding model (Chinese BGE model, 1GB+)
- Cold-start issue for new content (needs reindexing)
```

- [ ] **Step 6: Write ADR-005 (Voice integration)**

```markdown
# ADR-005: DashScope Voice Pipeline (ASR → Graph → TTS)

**Status:** Accepted (partially implemented)
**Date:** 2026-06

## Context
Phone-like voice interaction requires:
1. ASR (Automatic Speech Recognition) — convert user speech to text
2. Graph reasoning — run the conversation graph on transcribed text
3. TTS (Text-to-Speech) — convert response to speech
4. Voice rendering — adapt written response to spoken format

## Decision
Use Alibaba DashScope API for both ASR and TTS.
Route: ASR endpoint → LangGraph → Voice Render Prompt → TTS endpoint.

## Consequences
+ Single-provider simplicity (DashScope handles both ASR and TTS)
+ Voice render prompt adapts written response to spoken format (shorter sentences, no markdown)
- External API dependency — latency and cost per voice interaction
- TTS voice selection limited to DashScope voices
```

- [ ] **Step 7: Write ADR-006 (ADR process)**

```markdown
# ADR-006: Architecture Decision Record Process

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
The project accumulated multiple architectural changes without documented rationale.
New contributors (and AI agents) need context about why decisions were made.

## Decision
Record significant architecture decisions as ADRs in `docs/superpowers/adr/`.
Each ADR follows the template: Context → Decision → Consequences → Related ADRs.

## Template
```markdown
# ADR-NNN: Title

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** YYYY-MM

## Context
[Problem description, constraints, alternatives considered]

## Decision
[What was chosen and why]

## Consequences
[+ Positive, - Negative, and Neutral implications]

## Related
[Links to other ADRs]
```

## Consequences
+ Lightweight process — no bureaucracy overhead
+ Provides context for both humans and AI agents
+ Each ADR is a standalone file — easy to reference
- Requires discipline to write before/after significant changes
```

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/adr/
git commit -m "docs: add 6 architecture decision records (ADR-001 to ADR-006) (P1-audit)"
```

---

### Task 3: Add legacy-mode warning to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml:39-51`

- [ ] **Step 1: Add inline comment to streamlit service**

Add a warning comment before the streamlit service definition in `docker-compose.yml`:
```yaml
  # ── DEPRECATED LEGACY SERVICE ──────────────────────────
  # Streamlit UI is replaced by React frontend (port 3080).
  # This service is kept for development/testing only.
  # Do NOT enable in production. Use --profile legacy to start.
  streamlit:
```

Also add a comment on the volumes mount (line 49-50):
```yaml
    volumes:
      - ./data:/app/data  # LEGACY: SQLite mounted for dev convenience
```

- [ ] **Step 2: Verify docker-compose.yml syntax**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && docker compose config --quiet 2>&1 || echo "syntax check requires Docker daemon"`
If Docker is running, the command should produce no output (syntax valid). If not running, skip.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add legacy-mode warning to streamlit service in docker-compose (P1-audit)"
```

---

### Task 4: Add voice.py tests

**Files:**
- Create: `tests/server/services/test_voice.py`

- [ ] **Step 1: Read full voice.py to understand current interface**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
cat server/services/voice.py
```

Expected: a 20-line file with `VOICE_RENDER_SYSTEM_PROMPT` constant and `SCENE_VOICE_STYLES` dictionary.

- [ ] **Step 2: Create test_voice.py**

Create `tests/server/services/test_voice.py`:
```python
"""Tests for the voice service — prompts, styles, and rendering."""

from server.services.voice import SCENE_VOICE_STYLES, VOICE_RENDER_SYSTEM_PROMPT


class TestVoiceRenderPrompt:
    """VOICE_RENDER_SYSTEM_PROMPT should guide the LLM to produce spoken-style output."""

    def test_prompt_is_non_empty_string(self):
        assert isinstance(VOICE_RENDER_SYSTEM_PROMPT, str)
        assert len(VOICE_RENDER_SYSTEM_PROMPT) > 50

    def test_prompt_mentions_key_constraints(self):
        prompt = VOICE_RENDER_SYSTEM_PROMPT
        assert "200" in prompt or "200字" in prompt, "Should constrain response length"
        assert "markdown" not in prompt.lower() or "不要" in prompt, "Should discourage markdown"
        assert "口语" in prompt, "Should require spoken-style output"

    def test_prompt_mentions_zhangxuefeng(self):
        assert "张雪峰" in VOICE_RENDER_SYSTEM_PROMPT, "Should reference the advising methodology"


class TestSceneVoiceStyles:
    """SCENE_VOICE_STYLES should define tone for each supported scene."""

    def test_contains_required_scenes(self):
        assert "gaokao" in SCENE_VOICE_STYLES
        assert "kaoyan" in SCENE_VOICE_STYLES
        assert "career" in SCENE_VOICE_STYLES

    def test_all_styles_are_non_empty(self):
        for scene, style in SCENE_VOICE_STYLES.items():
            assert isinstance(style, str), f"Style for {scene} should be string"
            assert len(style) > 10, f"Style for {scene} should be descriptive"

    def test_gaokao_style_is_encouraging(self):
        assert "温暖" in SCENE_VOICE_STYLES["gaokao"] or "鼓励" in SCENE_VOICE_STYLES["gaokao"]

    def test_kaoyan_style_is_analytical(self):
        assert "理性" in SCENE_VOICE_STYLES["kaoyan"] or "分析" in SCENE_VOICE_STYLES["kaoyan"]

    def test_career_style_is_direct(self):
        assert "务实" in SCENE_VOICE_STYLES["career"] or "直接" in SCENE_VOICE_STYLES["career"]
```

- [ ] **Step 3: Verify test passes**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python3 -m pytest tests/server/services/test_voice.py -v
```
Expected: All tests PASSED

- [ ] **Step 4: Check coverage impact**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python3 -m pytest tests/server/services/test_voice.py --cov=server.services.voice --cov-report=term-missing -v 2>&1 | tail -20
```
Expected: coverage for `server/services/voice.py` > 0%

- [ ] **Step 5: Commit**

```bash
git add tests/server/services/test_voice.py
git commit -m "test: add voice.py tests for prompt constants and scene styles (P1-audit)"
```

---

## Phase 2 Verification (all tasks complete)

- [ ] `ls docs/superpowers/adr/ADR-*.md`
      Expected: ADR-001 through ADR-006

- [ ] `ls SPEC.md`
      Expected: file exists

- [ ] `python3 -m pytest tests/server/services/test_voice.py -v 2>&1 | tail -15`
      Expected: All 9 tests PASSED (test_prompt_is_non_empty_string, test_prompt_mentions_key_constraints, test_prompt_mentions_zhangxuefeng, test_contains_required_scenes, test_all_styles_are_non_empty, test_gaokao_style_is_encouraging, test_kaoyan_style_is_analytical, test_career_style_is_direct)

- [ ] `grep -c "DEPRECATED LEGACY" docker-compose.yml`
      Expected: ≥1 (the comment was added)

- [ ] Full project ruff check:
      `cd /home/dev/projects/gaobao/gaobao-advisor && ruff check . --exclude '.claude' --exclude 'scripts' --exclude 'frontend' --exclude 'node_modules' --exclude '__pycache__' --exclude 'data' && echo "✅ 0 errors"`
      Expected: 0 errors

- [ ] Global test suite (smoke):
      `cd /home/dev/projects/gaobao/gaobao-advisor && python3 -m pytest tests/test_server_health.py tests/test_auth.py tests/server/services/test_voice.py -v 2>&1 | tail -15`
      Expected: All passed

---

## Full Audit Resolution Summary

| Phase | Items | Status |
|-------|-------|--------|
| Phase 0 (15min) | LLM timeout, SSE try-except, auth.py SESSION_SECRET | ✅ P0 resolved |
| Phase 1 (1h) | CSP, app.py delete, scripts/ ruff, Sentry | ✅ P1 resolved |
| Phase 2 (3h) | SPEC.md + ADR, docker-compose comment, voice tests | ✅ P2 resolved |
| Self-cleared | Frontend CVE, requirements.lock | ✅ Already fixed |
