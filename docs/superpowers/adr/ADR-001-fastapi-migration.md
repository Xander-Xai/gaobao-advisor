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