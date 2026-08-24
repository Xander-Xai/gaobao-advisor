# Bugfix Plan — 2026-08-24

This plan tracks the static-audit findings on `master` and fixes them in dependency order.

## Phase 1 — Data contract and state persistence (P0/P1)

- [x] Normalize `score_rank` into canonical numeric `score` / `rank` fields while keeping `score_rank` for backwards compatibility.
- [x] Make `UserProfile` accept both legacy nested slots and current flat graph slots.
- [x] Preserve existing profile slots when persisting `_query_state`.
- [x] Return `_query_state` from the question node and persist it through the memory node.
- [x] Hydrate chat graph state from server-side persisted slots/query state instead of depending entirely on the frontend.
- [x] Add regression tests for score/rank normalization, flat-profile loading, and query-state preservation, including a DB-level `_query_state` persistence regression.

## Phase 2 — LLM streaming architecture (P0)

Implemented design:

1. Pre-generation graph: security → intent/scene → slot/profile → quality pre-check → data/RAG/reasoning → structured output.
2. Direct responses (security blocks or follow-up questions) bypass the main generation model.
3. Complete-profile requests enter real incremental `llm_node_stream` generation.
4. Source attribution and post-generation quality/judge/feedback/memory nodes run after generation.
5. The final assistant answer is persisted after generation and the user message is not duplicated in model memory.

Acceptance criteria:

- [x] Main complete-profile path enters the LLM generator.
- [x] Current user message is not duplicated in model memory.
- [x] Final streamed assistant answer is persisted.
- [x] Direct question/security replies still bypass the generation model.
- [x] Frontend parses SSE incrementally and updates the assistant message while tokens arrive.

## Phase 3 — Session ownership and endpoint authorization (P0)

- [x] Stop minting a valid token for an arbitrary existing client-selected `session_id`.
- [x] Introduce a server-owned session creation flow and require a valid session-bound token for chat requests.
- [x] Require session authorization for feedback/highlight mutations.
- [x] Ensure DB sessions close in `finally` and do not expose raw exception text to clients.
- [x] Add authorization regressions for missing tokens, cross-session takeover, stable tokens, feedback, and highlight.

## Phase 4 — Data API correctness (P1/P2)

- [x] Fix `AdmissionScore.major == <string>` relationship comparison by joining/filtering `Major.name`.
- [x] Type/validate cursor query parameters so malformed or negative cursors return 422 rather than 500.
- [x] Add seeded ORM regression coverage for major filtering and cursor validation.

## Phase 5 — Conversation termination and regression coverage

- [x] Enforce `MAX_QUERY_ROUNDS = 5` in Soul Query.
- [x] Stop falling back to the static question bank after the maximum round is reached.
- [x] Return a deterministic terminal prompt listing the still-missing fields.
- [x] Cover the max-round handoff and trace event with regression tests.
- [x] Cover canonical score extraction, profile completeness, persisted flat slots, real LLM streaming, session takeover rejection, data filtering, and `_query_state` preservation.

## Phase 6 — Dependency and CI hardening

- [x] Raise vulnerable backend dependency floors and lock versions for `aiohttp`, `cryptography`, `gitpython`, `langsmith`, and `pillow`.
- [x] Make backend `pip-audit` pass without weakening the audit policy.
- [x] Resolve frontend advisories in `brace-expansion`, `nanoid`, `postcss`, and `dompurify`; regenerate the lockfile.
- [x] Make frontend `npm audit` pass without changing the severity threshold.
- [x] Apply Ruff formatting to all files reported by the formatter while keeping `ruff check` clean.
- [ ] Confirm the final PR head passes the complete CI matrix after the last formatting/documentation commits.

## Merge strategy

Keep all work on `fix/bug-audit-20260824`; do not modify `master` directly. Keep PR #3 in draft until the final CI matrix is green. Once green, update the PR summary and mark it ready for review; do not merge into `master` without explicit approval.
