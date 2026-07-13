# Gaobao Advisor — 高考志愿 AI 顾问

## Overview

Gaobao Advisor is an AI-powered college application advisor for the Chinese Gaokao system. It combines a deep knowledge base (9 knowledge groups, 3,016+ schools, 215+ majors, 555+ expert quotes) with structured consultation logic to produce professional-grade admissions guidance — not just generic chatbot output.

The project targets Chinese high school students and their families making critical college/major choices. It runs as a FastAPI backend with a **Vue 3** SPA frontend, using **LangGraph** as the conversation state machine, deployed via Docker Compose with nginx reverse proxy.

## Architecture

### Service Layer
- **FastAPI server** (`server/main.py`) — primary HTTP entry point with async support, CORS, rate limiting, security middleware (injection detection, XSS sanitization, SSRF defense, CSP), and Sentry monitoring
- **LangGraph workflow** (`server/graph/graph.py`) — multi-node state machine for multi-turn conversation flow with conditional branching (profile completeness check), offline LLM reasoning + streaming token emission via `llm_node_stream`
- **SQLite database** (`db/database.py`) — embedded persistence with WAL mode; 13 tables covering schools, majors, admission scores, enrollment plans, graduate programs, career trends, conversations, feedback, highlights, yi-fen-yi-duan, and quality scores
- **Hybrid RAG** (`server/services/rag.py`) — vector + keyword knowledge retrieval with cache, 9 knowledge groups (G1-G9) and 555+ expert quotes
- **Voice pipeline** (`server/routes/voice.py`, `server/services/voice.py`) — WebSocket phone-mode path that accepts authenticated text frames, runs the graph, and optionally renders replies into oral style through a DashScope/OpenAI-compatible chat API; missing voice keys fail back to plain text
- **Quality modules** (`quality/`) — 7 modules: AI-era risk detection, anti-pattern checking, cross-validation, emotion detection, decision heuristics, model selector, and contextual knowledge loader
- **Skills framework** (`skills/`) — plugin-style skill modules with Gaokao-specific consulting logic (5 mental models, 8 heuristics, 8 anti-patterns, expression engine, safety rules)
- **Profile system** (`server/user_profile.py`, `server/routes/profile.py`) — 7-field user profiling (required: province, score, subject, interest; optional: region, family, goal) with SoulQuery engine (max 5 rounds)

### Frontend
- **Vue 3 SPA** (`frontend/`) — Pinia stores (chat/scene/voice/report), Tailwind CSS 4, SSE streaming chat with auto-scroll, WebSocket voice interaction via useVoice composable (LiveSubtitle + VoiceRipple, handles error messages from WebSocket), scene switching (gaokao/kaoyan/career/general), 4 routes (ChatView, ReportView, ProfileView, AdminView). Chat store handles SSE `error` and `degraded` events; report generation is triggered from ChatView; messages and session tokens are persisted to localStorage. The onboarding API (`POST /api/v1/onboarding`) exists on the backend but no frontend UI component consumes it yet.
- **nginx reverse proxy** — serves frontend static assets, proxies `/api/` to FastAPI, proxies `/ws/` with WebSocket upgrade

### Data Pipeline
- **Data importers** (`scrapers/`) — Baidu Gaokao parallel scrapers with checkpoint-based resume for 30 provinces
- **Database schema** — 13 tables (school, major, admission_score, enrollment_plan, subject_ranking, graduate_program, graduate_score, career_trend, yi_fen_yi_duan, conversation, conversation_message, feedback, highlight, quality_score)
- **Scripts** (`scripts/`) — 20+ import/validate/verify scripts for data pipeline operations

## Key Design Decisions

- **ADR-001**: FastAPI over Streamlit (separation of concerns, SSE streaming, concurrent connections)
- **ADR-002**: LangGraph workflow (state machine for multi-turn conversation)
- **ADR-003**: SQLite + WAL (zero-dependency embedded DB with concurrent readers)
- **ADR-004**: Hybrid RAG (vector + keyword for recall quality)
- **ADR-005**: DashScope Voice (ASR + TTS for phone-like interaction)
- **ADR-006**: HMAC session tokens (lightweight session ownership proof, no full auth system)

## API Contracts

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/health` | Health check (DB status + version) | None |
| POST | `/api/v1/chat` | SSE-streaming chat (LangGraph backed, two-phase) | None |
| POST | `/api/v1/chat/feedback` | Submit user feedback (helpful/not_helpful) | Bearer token |
| POST | `/api/v1/chat/highlight` | Extract golden quote from reply | Bearer token |
| GET | `/api/v1/data/schools` | School search (FTS + cursor pagination) | None |
| GET | `/api/v1/data/scores` | Admission scores query (cursor pagination) | None |
| GET | `/api/v1/data/plans` | Enrollment plan lookup (cursor pagination) | None |
| POST | `/api/v1/knowledge/search` | Knowledge base search (RAG with cache) | None |
| GET | `/api/v1/knowledge/quotes` | Quote attribution retrieval | None |
| POST | `/api/v1/onboarding` | User onboarding step submission | None |
| GET | `/api/v1/profile/{session_id}` | Get user profile + completeness | Bearer token |
| PUT | `/api/v1/profile/{session_id}` | Update single profile field | Bearer token |
| GET | `/api/v1/profile/{session_id}/next-question` | Get next soul query question | Bearer token |
| POST | `/api/v1/profile/{session_id}/skip` | Skip optional profile question | Bearer token |
| POST | `/api/v1/report/generate` | Generate advisory report | Body `session_id + token` |
| GET | `/api/v1/report/{report_id}` | Get report JSON | Query `session_id + token` |
| GET | `/api/v1/report/{report_id}/html` | Get HTML report page | Query `session_id + token` |
| GET | `/api/v1/report/{report_id}/cover.svg` | Get SVG cover image | Query `session_id + token` |
| WS | `/api/v1/ws/call` | Real-time voice call (ASR -> Graph -> TTS) | Query token |
| GET | `/metrics` | Prometheus metrics | None |

## LangGraph Workflow

The graph uses conditional branching at `profile_check`: incomplete profiles trigger a `question_generate -> render_reply -> memory_update` shortcut; complete profiles run the full quality -> data -> RAG -> reasoning -> structured output pipeline.

Nodes (17 total):
1. **security_scan** → injection detection on user input
2. **intent_detect** → classify user intent
3. **scene_route** → route to gaokao/kaoyan/career handler
4. **slot_extract** → extract profile fields from message
5. **profile_check** → conditional: complete? → full pipeline; incomplete? → question
6. **question_generate** → generate follow-up question via SoulQueryEngine
7. **quality_orchestrate** → quality pipeline orchestration (emotion, anti-pattern, cross-validation)
8. **data_query** → query school/major/score data
9. **rag_retrieve** → search knowledge base
10. **reason** → LLM reasoning with context
11. **structure_output** → format structured recommendations
12. **render_reply** → final rendering + post-processing
13. **source_attribution** → validate data source annotations
14. **quality_post_check** → LLM-as-Judge post-check (hallucination detection); conditional edge: if `should_rewrite` is true and `rewrite_attempts < 1`, routes back to `render_reply` for re-generation; otherwise proceeds to `quality_judge`
15. **quality_judge** → LLM-as-Judge quality scoring (4 dimensions)
16. **feedback** → user feedback routing (helpful/not_helpful)
17. **memory_update** → persist conversation to DB

## Two-Phase Streaming

The `/api/v1/chat` endpoint uses a two-phase architecture:
1. **Phase 1 (Graph phase):** `graph.invoke()` runs the LangGraph pipeline synchronously inside the SSE generator, producing structured metadata (slots, emotion, structured card). The quality judge fails closed to unscored defaults when no judge API key is configured or when a sync graph node is already inside a running event loop.
2. **Phase 2 (Streaming):** LLM tokens are streamed in real-time via `llm_node_stream()` — the LLM is NOT called during graph.invoke(), avoiding double LLM calls

SSE events emitted: `slots`, `emotion`, `structured`, `token`, `error`, `degraded`, `quality`, `done` (with HMAC-signed session_token). The `error` and `degraded` events are handled by the frontend chat store to surface issues to the user.

## HMAC Session Authentication

- Client receives `session_token` in SSE `done` event
- Token is HMAC-SHA256 signature of `session_id` using `SESSION_SECRET`
- Auth helpers are centralized in `server/auth.py` (`require_bearer_auth` and `require_token_auth`), eliminating duplication across route files
- Profile, feedback, and highlight endpoints require `Authorization: Bearer <token>`
- Report generation requires body `session_id + token`; report read/export endpoints require query `session_id + token`
- Voice WebSocket requires query `session_id + token`
- Multi-worker deployments must share the same `SESSION_SECRET`

## Data Flow

```
User (browser/mobile)
  |
  v
nginx (:80)
  |-- /api/*  --> FastAPI (port 8000)
  |                |-- /api/v1/chat      --> LangGraph workflow + SSE stream
  |                |-- /api/v1/data/*    --> SQLite (schools, scores, plans)
  |                |-- /api/v1/knowledge/* --> Hybrid RAG (G1-G9 + quotes)
  |                |-- /api/v1/profile/* --> SQLite (user_profile slots)
  |                |-- /api/v1/report/*  --> JSON file storage + HTML/SVG export
  |-- /ws/*       --> FastAPI (WS)
  |                     |-- /api/v1/ws/call     --> VoiceService (ASR -> Graph -> TTS)
  |-- /           --> Vue 3 SPA (port 80)
```

## Deployment

- **Docker Compose** — three services: `api` (FastAPI), `frontend` (nginx serving Vue 3), `nginx` (reverse proxy on port 80)
- **Environment config** via `.env` (LLM API key, DashScope key, Sentry DSN, CORS origins)
- **No external DB dependency** — SQLite file lives in `./data/`
- **Security headers** configured in nginx (HSTS, CSP, X-Frame-Options, etc.)

See [deployment-guide.md](docs/deployment-guide.md) and [deploy-checklist.md](docs/deploy-checklist.md) for details.

## Testing Strategy

- **pytest** with httpx ASGI transport for integration tests (817 collected tests; latest verification: **816 passed, 1 skipped**, coverage **77.78%**)
- Key test suites:
  - `tests/test_agent_core.py` — core agent logic
  - `tests/test_chat_sse.py` — SSE streaming chat
  - `tests/test_langgraph.py` — LangGraph workflow
  - `tests/test_middleware_*` — security and rate limiting middleware
  - `tests/test_integration_e2e.py` — end-to-end conversation flows
  - `tests/test_integration_rag.py` — RAG retrieval quality
  - `tests/test_quality_*.py` — quality module unit tests
  - `tests/test_quote_attribution.py` — source attribution
  - `tests/test_source_attribution.py` — data source validation
  - `tests/test_g9_retrieval.py` — G9 knowledge group retrieval
  - `tests/test_auth_endpoints.py` — authentication tests
- Target: 70%+ coverage (enforced via pytest-cov)
