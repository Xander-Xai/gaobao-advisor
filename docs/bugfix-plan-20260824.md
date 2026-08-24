# Bugfix Plan — 2026-08-24

This plan tracks the static-audit findings on `master` and fixes them in dependency order.

## Phase 1 — Data contract and state persistence (P0/P1)

- [x] Normalize `score_rank` into canonical numeric `score` / `rank` fields while keeping `score_rank` for backwards compatibility.
- [x] Make `UserProfile` accept both legacy nested slots and current flat graph slots.
- [x] Preserve existing profile slots when persisting `_query_state`.
- [x] Return `_query_state` from the question node and persist it through the memory node.
- [x] Hydrate chat graph state from server-side persisted slots/query state instead of depending entirely on the frontend.
- [ ] Add regression tests for score/rank normalization, flat-profile loading, and query-state preservation.

## Phase 2 — LLM streaming architecture (P0)

Current graph reaches `render_reply` before `chat.py` decides whether to call `llm_node_stream`, so the normal LLM streaming branch is effectively unreachable.

Target design:

1. Pre-generation graph: security → intent/scene → slot/profile → quality pre-check → data/RAG/reasoning → structured output.
2. If the route is a direct response (security block or follow-up question), stream that reply directly.
3. Otherwise stream the LLM answer from the prepared state.
4. After generation, run source attribution / post quality checks / judge / feedback.
5. Persist the user message and the final assistant answer exactly once, after generation.

Acceptance criteria:

- Main complete-profile path enters the LLM generator.
- Current user message is not duplicated in model memory.
- Final streamed assistant answer is persisted.
- Direct question/security replies still bypass the generation model.

## Phase 3 — Session ownership and endpoint authorization (P0)

- [ ] Stop minting a valid token for an arbitrary existing client-selected `session_id`.
- [ ] Introduce a server-owned session creation/first-turn flow or require a valid token for existing sessions.
- [ ] Require session authorization for feedback/highlight mutations.
- [ ] Ensure DB sessions close in `finally` and do not expose raw exception text.

## Phase 4 — Data API correctness (P1/P2)

- [ ] Fix `AdmissionScore.major == <string>` relationship comparison by joining/filtering `Major.name`.
- [ ] Type/validate cursor query parameters so malformed cursors return 4xx rather than 500.

## Phase 5 — Regression and integration coverage

Add tests covering:

- `河北考生600分物理类想学计算机` produces canonical `score == 600`.
- A completed profile does not incorrectly request score again.
- Admission matching is invoked when province/score/subject are present.
- Persisted flat slots are restored on the next turn.
- `_query_state.round_count` survives multiple requests and never erases profile slots.
- Complete-profile chat takes the real LLM streaming path.
- Existing-session takeover attempt without a valid token is rejected.
- `/data/scores?major=...` and malformed cursor behavior.

## Merge strategy

Keep all work on `fix/bug-audit-20260824`; do not modify `master` directly. After tests pass, open one PR with commits grouped by phase so individual fixes remain reviewable/revertible.
