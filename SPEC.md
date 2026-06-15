# Gaobao Advisor — 高考志愿 AI 顾问

## Overview

Gaobao Advisor is an AI-powered college application advisor for the Chinese Gaokao system. It combines a deep knowledge base (17+ modules from 8 books, 61 video courses, 2,600+ schools, 792 majors) with structured consultation logic to produce professional-grade admissions guidance — not just generic chatbot output.

The project targets Chinese high school students and their families making critical college/major choices. It runs as a FastAPI backend with a React SPA frontend, deployed via Docker Compose with nginx reverse proxy.

## Architecture

### Service Layer
- **FastAPI server** (`server/main.py`) — primary HTTP entry point with async support, CORS, rate limiting, security middleware, and Sentry monitoring
- **LangGraph workflow** (`server/graph/graph.py`) — state machine for multi-turn conversation flow with LLM node streaming
- **SQLite database** (`db/database.py`) — embedded persistence with WAL mode; schema covers schools, majors, admission scores, user profiles, and onboarding state
- **Hybrid RAG** (`server/services/rag.py`) — vector + keyword knowledge retrieval over 2.7MB of extracted text from expert books and video transcripts
- **Voice pipeline** (`server/services/voice.py`) — WebSocket-based ASR -> Graph -> TTS loop using DashScope API for phone-like interaction
- **Quality modules** (`quality/`) — AI-era risk detection, anti-pattern checking, cross-validation, emotion detection, and model selector for consultation quality assurance
- **Skills framework** (`skills/`) — plugin-style skill modules with Gaokao-specific consulting logic
- **Profile system** (`server/user_profile.py`, `server/routes/profile.py`) — multi-step user profiling for personalized recommendations

### Frontend
- **React SPA** (`frontend/`) — mobile-first chat UI with smooth animations and voice interaction support
- **nginx reverse proxy** (`nginx.conf`) — serves frontend static assets, proxies `/api/` to FastAPI, proxies `/ws/` with WebSocket upgrade

### Data Pipeline
- **Data importers** (`scrapers/`) — Baidu Gaokao parallel scrapers with checkpoint-based resume for 30 provinces
- **Database schema** — schools, majors, admission scores, enrollment plans with full-text search

## Key Design Decisions

See `docs/superpowers/adr/ADR-001-fastapi-migration.md`:
- **ADR-001**: FastAPI over Streamlit (separation of concerns, SSE streaming, concurrent connections)
- **ADR-002**: LangGraph workflow (state machine for multi-turn conversation)
- **ADR-003**: SQLite + WAL (zero-dependency embedded DB with concurrent readers)
- **ADR-004**: Hybrid RAG (vector + keyword for recall quality)
- **ADR-005**: DashScope Voice (ASR + TTS for phone-like interaction)

## API Contracts

| Method | Path | Description | File |
|--------|------|-------------|------|
| GET | `/api/v1/health` | Health check | `server/routes/health.py` |
| POST | `/api/v1/chat` | SSE-streaming chat (LangGraph backed) | `server/routes/chat.py` |
| GET | `/api/v1/data/schools` | School search | `server/routes/data.py` |
| GET | `/api/v1/data/scores` | Admission scores query | `server/routes/data.py` |
| GET | `/api/v1/data/plans` | Enrollment plan lookup | `server/routes/data.py` |
| POST | `/api/v1/knowledge/search` | Knowledge base search (RAG) | `server/routes/knowledge.py` |
| GET | `/api/v1/knowledge/quotes` | Quote attribution retrieval | `server/routes/knowledge.py` |
| POST | `/api/v1/onboarding` | User onboarding submission | `server/routes/onboarding.py` |
| GET | `/api/v1/profile/{session_id}` | Get user profile | `server/routes/profile.py` |
| PUT | `/api/v1/profile/{session_id}` | Update user profile | `server/routes/profile.py` |
| GET | `/api/v1/profile/{session_id}/next-question` | Get next profiling question | `server/routes/profile.py` |
| POST | `/api/v1/profile/{session_id}/skip` | Skip profiling question | `server/routes/profile.py` |
| WS | `/ws/call` | Real-time voice call (ASR -> Graph -> TTS) | `server/routes/voice.py` |

## Data Flow

```
User (browser/mobile)
  |
  v
nginx (:80)
  |-- /api/*  --> FastAPI (port 8000)
  |                |-- /api/v1/chat      --> LangGraph workflow --> LLM + RAG
  |                |-- /api/v1/data/*    --> SQLite (schools, scores, plans)
  |                |-- /api/v1/knowledge/* --> Hybrid RAG service
  |                |-- /api/v1/profile/* --> SQLite (user_profiles)
  |                |-- /api/v1/onboarding --> SQLite (onboarding)
  |                |-- /api/v1/health    --> in-memory status
  |-- /ws/*       --> FastAPI (WS)
  |                     |-- /ws/call     --> VoiceService (ASR -> Graph -> TTS)
  |-- /           --> React SPA (port 80)
```

## Deployment

- **Docker Compose** — three services: `api` (FastAPI), `frontend` (nginx serving React), `nginx` (reverse proxy on port 80)
- **Environment config** via `.env` (DashScope API key, Sentry DSN, CORS origins)
- **No external DB dependency** — SQLite file lives in `./data/`
- **Security headers** configured in nginx (HSTS, CSP, X-Frame-Options, etc.)

## Testing Strategy

- **pytest** with httpx ASGI transport for integration tests (48 test files)
- Key test suites:
  - `tests/test_agent_core.py` — core agent logic
  - `tests/test_chat_sse.py` — SSE streaming chat
  - `tests/test_langgraph.py` — LangGraph workflow
  - `tests/test_middleware_*` — security and rate limiting middleware
  - `tests/test_integration_e2e.py` — end-to-end conversation flows
  - `tests/test_integration_rag.py` — RAG retrieval quality
  - `tests/test_quality_*.py` — quality module unit tests
  - `tests/test_quote_attribution.py` — source attribution
  - `tests/test_p1_features.py`, `tests/test_p2_features.py` — phased feature validation
- Target: 70%+ coverage (enforced via pytest-cov)
