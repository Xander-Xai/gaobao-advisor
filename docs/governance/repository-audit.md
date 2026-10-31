# Repository governance audit — 2026-10-31

> Scope: `Xander-Xai/gaobao-advisor`, default branch `master`.
> This ledger records the state found in Phase 0, the asset decision, and the
> final action. It is intentionally factual; branch/PR/issue state must be
> rechecked after every mutation.

## 0. Verified post-governance baseline (2026-10-31)

| Item | Observed |
|---|---|
| Default branch | `master` |
| `master` SHA | `f43be0128e7fd853097cce009a1417bf1245515f` (verified before the follow-up PR) |
| Open PRs | 0 |
| Open issues | #36–#40 |
| Closed issues | #10, #22, #24 |
| Remote branches | 1 (`master`) + archive tag |
| Worktrees | only `/home/dev/projects/gaobao/gaobao-advisor` |
| Branch protection | **ENABLED** on `master` (required checks, no force/delete, admins enforced) |
| Required checks | 9: Lint, Test 3.10/3.11, MySQL+Redis+Admin Smoke, Security, Secret, Frontend, Container, Redistribution |
| Baseline master CI | **9/9 SUCCESS** (`f43be01`, [run 41123250301](https://github.com/Xander-Xai/gaobao-advisor/actions/runs/41123250301)) |
| PR #35 CI | 9/9 success at `1f3afab` (run 41119912593), merged `b98225a` |
| PR #31 CI | 9/9 success at `51b8936` (run 41120400909), merged `4d05916` |

## 1. Remote branch inventory

| Branch | HEAD | merge-base | ahead/behind vs master | Unique assets | Decision |
|---|---|---|---|---|---|
| `master` | `f43be01` | — | — | canonical baseline; full SHA in Section 0 | protected by process; no force push |
| `fix/haibote-acceptance-hardening-20261031` | `1f3afab` | `1622c3f` | merged via #35 | PR #35 fixes + reliability work | **deleted** after merge |
| `docs/portfolio-reference-boundaries-20261030` | `51b8936` | `65bdb40` | merged via #31 | README boundary section only | **deleted** after merge |
| `feat/vue3-ts-readonly-data-workbench-20261030` | `8fe4f61` | `65bdb40` | 1 ahead / 10 behind | old read-only TS prototype + design doc | **deleted**; archived tag `archive/vue3-ts-readonly-20261030` |
| `feat/haibote-phase1-admin-workbench-20261030` | `4b81aaa` | `4b81aaa` | ancestor of master | none | **deleted** |
| `feat/haibote-phase2-mysql-redis-worker-20261030` | `aab68c2` | `aab68c2` | ancestor of master | none | **deleted** |
| `feat/haibote-phase3-acceptance-20261030` | `4a3c6d5` | `4a3c6d5` | ancestor of master | none | **deleted** |

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
| #35 | **MERGED** | `1f3afab` | merged `b98225a`; CI 9/9 |
| #31 | **MERGED** | `51b8936` | merged `4d05916`; CI 9/9 |
| #41 | **MERGED** | — | governance ledger, merged `d41f4ef` |
| #42 | **MERGED** | — | branch protection documentation, merged `f43be01` |
| #34/#33/#32 | MERGED | — | verify commits in master; phase branches deletable |
| #30/#29/#28/#27/#26/#25/#23/#21/#20/#19/#18/#17/#16/#15/#14/#13/#12/#11/#9/#8/#7/#6/#4/#2/#1 | MERGED | — | no action |
| #5 | CLOSED (draft, conflicting) | — | record; no unique asset to merge |
| #3 | CLOSED (unmerged) | — | record; no unique asset to merge |

No review threads or explicit approval submissions existed on #35/#31 when
reviewed. That was a historical governance gap, not the final state: `master`
protection was subsequently enabled, with required checks as recorded below.
The connected GitHub read-only inventory does not independently expose the
protection-rule details; re-check GitHub branch settings before relying on them.

## 3. Issue inventory

| Issue | State | Evidence | Decision |
|---|---|---|---|
| #10 session token ownership | CLOSED | PR #11 + `tests/test_auth*` | keep closed; re-verify in final suite |
| #22 version/RAG wording drift | CLOSED | PR #23, `pyproject.toml` 3.0.0 | keep closed |
| #24 synthetic E2E/no-key behavior | CLOSED | PR #25, `test_public_demo_acceptance.py` | keep closed |

Open issues at audit time: **0**. After audit, 5 executable long-term issues
were created (no duplicates): #36 MySQL historical migration, #37 full Compose
in CI, #38 capacity/load benchmarks, #39 distributed rate limit/token
revocation, #40 consumer-group ACK evaluation. Closed #10/#22/#24 were
re-verified and commented with current master evidence; they remain closed.

## 4. CI/CD and security snapshot

- Workflow: `.github/workflows/ci.yml`, 9 jobs.
- `master@1622c3f` failed `Security Audit`: legacy Pillow 12.3.0, 31 advisories.
- PR #35 branch already contains `streamlit 1.66.1 + pillow 13.0.0`,
  `dompurify 3.4.17`, production Compose credential tests, MySQL/Redis/admin
  integration job, and the earlier reliability compensation.
- Required checks/branch protection: **ENABLED** on 2026-10-31 with the 9 CI
  jobs, `strict=true`, `enforce_admins=true`, no force push, no branch deletion,
  conversation resolution required. No protection rule was bypassed.
- No real secrets are committed; `.env*` production files are gitignored.

## 5. Action log

| Time | Action | Result |
|---|---|---|
| Phase 0 | fetched all refs via SSH; pruned stale tracking | 7 remote branches confirmed |
| Phase 0 | audited PR/Issue/review threads/branch protection | no review threads, no protection, 0 open issues |
| Phase 1 | reliability code + tests | committed `1f3afab`; full suite 1085/14; integration 13 |
| Phase 3 | PR #35 merge | **MERGED** `b98225a`; CI 9/9 (run 41119912593) |
| Phase 3 | PR #31 sync/merge | **MERGED** `4d05916`; CI 9/9 (run 41120400909) |
| Phase 4 | branch cleanup | 6 remote branches deleted; archive tag pushed; only `master` remains |
| Phase 5 | issue governance | #36–#40 created; #10/#22/#24 re-verified/commented |
| Phase 7 | final master verification | pytest 1085/14, coverage 81.11%; frontend 86; integration 13; CI success 41120768687 |
| Phase 7 | branch protection | enabled on `master`: 9 required checks, strict, enforce admins, no force/delete |

## 6. Rollback and safety

- No force push, no history rewrite, no deletion before asset check.
- PR #35 was merged with a **merge commit** (`b98225a69c0f3dc4e82e1763e9d9f9cad31d8e75`),
  not a linear or squash range. If a rollback is actually required, first inspect
  dependent commits, branch protection, database compatibility and current refs;
  the merge-specific command is `git revert -m 1 b98225a69c0f3dc4e82e1763e9d9f9cad31d8e75`.
  Do **not** run it blindly: subsequent PRs may depend on the change. A squash
  commit instead uses `git revert <squash_sha>`, while ordinary linear commits
  must be identified in the actual landed history. The historical expression
  `1622c3f..<merge-base>` was not a valid general rollback recipe.
- Branch deletion is recoverable from the recorded SHA; phase branches are
  ancestors of `master` and already merged.
- Local `.env.full` is generated, gitignored, mode 0600, and restored after
  Compose tests; no test secrets are committed.

## 7. Follow-up work: full Compose CI

- Baseline observed from GitHub before this work: `master@f43be01`, 0 open PRs,
  1 remote branch (`master`), 5 open issues (#36–#40), and 9 successful CI jobs
  in run 41123250301.
- [Issue #37](https://github.com/Xander-Xai/gaobao-advisor/issues/37) tracks
  full-profile Compose automation. The follow-up changes are prepared through
  a protected PR workflow, not an unreviewed direct `master` commit.
- The new `Full Compose E2E` job is additional to the existing nine jobs; its
  status and any decision to close #37 must be based on the **new PR run**,
  not on the earlier baseline run.
- Remaining #36 and #38–#40 stay open until their own acceptance criteria are
  independently satisfied. No production SLA or full historic MySQL migration
  is implied by a passing Compose smoke test.
