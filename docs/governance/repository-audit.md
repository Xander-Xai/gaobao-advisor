# Repository governance audit — 2026-10-31

> Scope: `Xander-Xai/gaobao-advisor`, default branch `master`.
> This ledger records the state found in Phase 0, the asset decision, and the
> final action. It is intentionally factual; branch/PR/issue state must be
> rechecked after every mutation.

## 0. Snapshot

| Item | Observed |
|---|---|
| Default branch | `master` |
| `master` SHA | `1622c3f04dd9931d69134d34e97c78b07d5d20a1` |
| Open PRs | #35, #31 |
| Open issues | 0 |
| Closed issues | #10, #22, #24 |
| Remote branches | 7 including `master` |
| Worktrees | only `/home/dev/projects/gaobao/gaobao-advisor` |
| Branch protection | **none** (`GET /branches/master/protection` → 404) |
| Required checks | **none configured** (no branch protection) |
| Latest master CI | **FAILED** (`Security Audit`, Pillow 12.3.0 advisories) |
| PR #35 CI | 9/9 success at `fa4c19f` before this reliability round |
| PR #31 CI | failed on old base (`e62d94a`); branch is 10 behind master |

## 1. Remote branch inventory

| Branch | HEAD | merge-base | ahead/behind vs master | Unique assets | Decision |
|---|---|---|---|---|---|
| `master` | `1622c3f` | — | — | canonical | protected by process; no force push |
| `fix/haibote-acceptance-hardening-20261031` | `fa4c19f` → reliability commits | `1622c3f` | ahead | PR #35 fixes + this reliability work | merge after CI |
| `docs/portfolio-reference-boundaries-20261030` | `e62d94a` | `65bdb40` | 1 ahead / 10 behind | README boundary section only | sync with master, then merge or close SUPERSEDED |
| `feat/vue3-ts-readonly-data-workbench-20261030` | `8fe4f61` | `65bdb40` | 1 ahead / 10 behind | old read-only TS prototype + design doc | superseded by Phase 1–3 admin workbench; archive SHA, then delete |
| `feat/haibote-phase1-admin-workbench-20261030` | `4b81aaa` | `4b81aaa` | 0 ahead / 8 behind | none (ancestor of master) | delete after PR #32 merged evidence |
| `feat/haibote-phase2-mysql-redis-worker-20261030` | `aab68c2` | `aab68c2` | 0 ahead / 6 behind | none (ancestor of master) | delete after PR #33 merged evidence |
| `feat/haibote-phase3-acceptance-20261030` | `4a3c6d5` | `4a3c6d5` | 0 ahead / 5 behind | none (ancestor of master) | delete after PR #34 merged evidence |

Local stale branches `docs/mark-private-env-docs-historical-20261021` and
`fix/dependency-security-runtime-20261021` point at already-merged commits and
their remote refs are gone; they are safe to prune locally after the audit.

### Vue/TS prototype semantic review

The prototype branch predates the admin workbench. Its unique files are:

- `frontend/src/api/admin.ts` — typed public `/data/schools` cursor client,
  runtime response validation, AbortSignal support.
- `frontend/src/views/AdminView.vue` — read-only health + school list, filters,
  cursor pagination, loading/empty/error/retry.
- `frontend/src/api/__tests__/admin.test.ts`,
  `frontend/src/views/__tests__/AdminView.spec.ts`, `frontend/tsconfig.json`.
- `docs/frontend-vue3-ts-upgrade.md` — design/evidence note.

The current `master` admin workbench (PR #32/#35) already provides typed
`frontend/src/api/admin.ts`, `stores/admin.ts`, DTOs, auth/RBAC, offset
pagination, quality jobs, review and audit, with 86 Vitest tests and
`vue-tsc`. The prototype's cursor client targets a different public endpoint
and would conflict with the admin API. **Decision: do not merge the old
AdminView.** Preserve the prototype commit SHA (`8fe4f61`) and this asset
summary in the governance ledger; delete the remote branch only after the
reliability PR is merged and no PR depends on it.

## 2. PR inventory

| PR | State | Head | Action |
|---|---|---|---|
| #35 | OPEN / CLEAN | `fa4c19f` (+ reliability commits) | audit diff, add reliability work, run full CI, merge |
| #31 | OPEN / UNSTABLE | `e62d94a` | merge master into branch (no force), resolve README, validate links/CI, then merge or close SUPERSEDED |
| #34/#33/#32 | MERGED | — | verify commits in master; phase branches deletable |
| #30/#29/#28/#27/#26/#25/#23/#21/#20/#19/#18/#17/#16/#15/#14/#13/#12/#11/#9/#8/#7/#6/#4/#2/#1 | MERGED | — | no action |
| #5 | CLOSED (draft, conflicting) | — | record; no unique asset to merge |
| #3 | CLOSED (unmerged) | — | record; no unique asset to merge |

No review threads exist on #35 or #31. Neither PR has an explicit review
approval; repository has no branch protection or required checks. This is a
governance gap: CI success is the only current merge gate.

## 3. Issue inventory

| Issue | State | Evidence | Decision |
|---|---|---|---|
| #10 session token ownership | CLOSED | PR #11 + `tests/test_auth*` | keep closed; re-verify in final suite |
| #22 version/RAG wording drift | CLOSED | PR #23, `pyproject.toml` 3.0.0 | keep closed |
| #24 synthetic E2E/no-key behavior | CLOSED | PR #25, `test_public_demo_acceptance.py` | keep closed |

Open issues at audit time: **0**. Long-term gaps (14-table MySQL migration,
full Compose in CI, capacity testing, distributed rate limit/token revocation)
need executable issues if not completed in this round; deduplicate before
creating.

## 4. CI/CD and security snapshot

- Workflow: `.github/workflows/ci.yml`, 9 jobs.
- `master@1622c3f` failed `Security Audit`: legacy Pillow 12.3.0, 31 advisories.
- PR #35 branch already contains `streamlit 1.66.1 + pillow 13.0.0`,
  `dompurify 3.4.17`, production Compose credential tests, MySQL/Redis/admin
  integration job, and the earlier reliability compensation.
- Required checks/branch protection: none; final report must state this
  explicitly rather than claiming protected branch enforcement.
- No real secrets are committed; `.env*` production files are gitignored.

## 5. Action log

| Time | Action | Result |
|---|---|---|
| Phase 0 | fetched all refs via SSH; pruned stale tracking | 7 remote branches confirmed |
| Phase 0 | audited PR/Issue/review threads/branch protection | no review threads, no protection, 0 open issues |
| Phase 1 | reliability code + tests (this branch) | pending commit/CI |
| Phase 3 | PR #35 merge | pending |
| Phase 3 | PR #31 sync/decision | pending |
| Phase 4 | phase/Vue branch cleanup | pending |
| Phase 5 | issue creation/updates | pending |
| Phase 7 | final master verification | pending |

## 6. Rollback and safety

- No force push, no history rewrite, no deletion before asset check.
- PR #35 rollback: revert `1622c3f..<merge-base>` using older..newer range
  after merge; for squash merge revert the squash commit.
- Branch deletion is recoverable from the recorded SHA; phase branches are
  ancestors of `master` and already merged.
- Local `.env.full` is generated, gitignored, mode 0600, and restored after
  Compose tests; no test secrets are committed.
