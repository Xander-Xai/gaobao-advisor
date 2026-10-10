# Open-source readiness

Status date: 2026-07-13

This document is the evidence ledger for preparing the community developer
edition. A checked item means that current commands or files prove the claim;
historical reports are not sufficient evidence.

## Release boundary

- Current implementation branch: `codex/open-source-readiness`.
- The existing private repository history remains intact.
- The public candidate is produced as a clean Git archive from the release
  branch. Rewriting the existing repository history is not automatic.
- Creating a remote repository, pushing, making it public, publishing images,
  or creating a release requires final user authorization.
- The working tree contained pre-existing uncommitted development work when
  this effort began. Open-source commits stage only explicitly reviewed files.

## Reproducible audit

Run the local structural audit:

```bash
bash scripts/audit_open_source.sh
```

Run the release audit with complete-history secret scanning:

```bash
bash scripts/audit_open_source.sh --history --require-gitleaks
```

The second command is a release gate. A machine without Gitleaks cannot mark
the secret-scanning requirement as passed; CI provides the same gate.

## Initial high-risk inventory

| Category | Current evidence | Risk | Disposition |
| --- | --- | --- | --- |
| Database | `data/gaokao.db.corrupted` was tracked at about 86 MB | Unknown contents, repository bloat | Remove from public candidate; keep local file until owner confirms disposal |
| Backups | Two tracked SQL gzip archives under `backups/` | May contain licensed data or personal information | Remove from public candidate; do not publish |
| Reports | 34 tracked report JSON files and additional local generated reports | May contain profiles, conversation-derived content or session identifiers | Remove from public candidate and ignore the entire runtime directory |
| Local agent state | A tracked `.claude/worktrees/` gitlink | Couples the repository to a local worktree and may expose tool state | Remove from public candidate; preserve the local worktree |
| Secrets | Configuration examples plus repository history | Deleted credentials may remain in history | Scan working tree and complete history with Gitleaks; rotate any confirmed credential |
| Knowledge content | `knowledge/`, quote collections and prompts | Third-party text may not inherit the MIT code license | Classify in `THIRD_PARTY_NOTICES.md` before release |
| Data adapters | Baidu and other external data integrations | API access does not imply redistribution rights | Publish adapters only until data rights are documented |
| Branding | gaobao and references to third-party personalities | Risk of implied endorsement | Add an explicit trademark and non-affiliation statement |

## Asset classes

- **Code:** Python, Vue, configuration loaders, tests and deployment tooling.
- **Data:** databases, JSON/CSV datasets, embeddings and imported source data.
- **Content:** prompts, knowledge articles, quotes, images and marketing copy.
- **Runtime artifacts:** reports, logs, sessions, caches, test output and local
  monitoring state.
- **Restricted assets:** production data, backups, personal information,
  credentials, and material without a confirmed redistribution basis.

## Checkpoint A: release baseline

- [x] Reproducible asset and risk audit is available.
- [x] Public candidate and private-history boundaries are documented.
- [x] No history rewrite or remote publication was performed.

## Checkpoint B: repository hygiene and secret safety

- [x] Runtime artifacts are ignored by Git and Docker contexts.
- [x] Restricted and oversized artifacts are not tracked in the public candidate.
- [x] Working-tree Gitleaks scan passes: Gitleaks v8.30.1 scanned the 5.11 MB
  non-ignored candidate on 2026-07-11 and found no leaks.
- [x] Complete-history Gitleaks scan passes: 366 commits and 11.63 MB were
  scanned on 2026-07-11 with no leaks after the exact placeholder dispositions
  below. Every future finding must have a documented,
  reviewed disposition and any exposed credential has been rotated.

### Secret scan dispositions

- The two documented Slack webhook examples use literal `YOUR/WEBHOOK/URL` or
  `T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX` placeholder segments. Only
  those exact values are allowlisted.
- `Bearer YOUR_TOKEN` is an exact API documentation placeholder. Only that
  exact value is allowlisted.

### Local preservation evidence

- The two SQL archives and corrupted database remained on disk after being
  removed from the Git index; all three SHA-256 checks passed.
- All 207 local report files remained on disk and passed their SHA-256 checks.
- The local `.claude/worktrees/` directory remained present after its gitlink
  was removed from the Git index.

## Release gates

- [x] Code, data, content, third-party and brand rights are classified in
  `config/open_source_assets.tsv` and the root policy documents. Assets marked
  `exclude` are omitted from the final public archive.
- [x] Security, privacy, support and community governance documents are complete.
- [x] README links to every policy document and documents the no-key path.
- [x] No-key demo configuration and synthetic sample data are verified.
- [x] Backend, frontend, container and supply-chain CI gates pass.
- [x] README and release documentation match the verified implementation.
- [x] High-stakes education output and privacy controls pass their fixed tests.
- [x] A clean candidate copy passes every local completion criterion in the design.

## Checkpoint C: rights and governance

- [x] Tracked data, content and visual assets have an automated classification.
- [x] Data licensing, provenance, third-party and non-affiliation boundaries are
  documented without extending MIT to third-party assets.
- [x] Security, privacy, support, conduct, ownership and changelog files exist.
- [x] Public issue and pull-request templates warn against secrets and personal
  data and require provenance for new data contributions.
- [x] README links the public policy surface.

## Resolved quality blockers

- The initial 19 Ruff errors were reconciled; `ruff check .` and
  `ruff format --check .` pass for 237 public Python files.
- DOMPurify was raised to 3.4.12 and the deprecated icon package was replaced;
  the frontend moderate-level audit reports zero vulnerabilities.
- LangSmith was raised to 0.8.18 after `pip-audit` identified
  `GHSA-f4xh-w4cj-qxq8`; the final lock-file audit reports no known vulnerabilities.

## Checkpoint D: no-key demo path

- [x] Default configuration uses the deterministic `demo` provider, keyword
  retrieval fallback and disabled voice/search integrations; no API key is
  required.
- [x] Production startup validation rejects missing `SESSION_SECRET` and
  `CORS_ORIGINS`; monitoring rejects a default Grafana admin password.
- [x] The CC0 dataset contains 3 synthetic schools, 3 synthetic majors and 6
  synthetic score records. Seeding twice is idempotent and all institutions
  are visibly marked as examples.
- [x] Twelve focused configuration, seed and health tests pass; 26 auth, route,
  SSE and integration regression tests also pass.
- [x] Docker build contexts were reduced from about 467 MB/170 MB to about
  82 KB/4 KB for backend/frontend rebuilds.
- [x] Backend and frontend images build successfully. In a real Compose run,
  the API became healthy with `mode=demo`, the frontend returned HTTP 200, the
  database contained `3|3|6`, and SSE output disclosed “社区演示模式”, “合成示例”
  and “非官方工具”.
- [x] Demo containers and named demo-data volumes were removed after final verification.

## Checkpoint E: automated quality and supply-chain gates

- [x] Required CI jobs cover complete-history Gitleaks, Ruff, Python tests and
  coverage, frontend tests/build/audit, dependency licenses, documentation,
  Compose validation and a no-key container smoke test.
- [x] Frontend clean-lock verification passes: 48 tests, Vite production build
  and `npm audit --audit-level=moderate` with zero vulnerabilities.
- [x] Python dependency audit reports no known vulnerabilities; the dependency
  license inventory contains no prohibited or unreviewed identifiers.
- [x] Documentation validation rejects placeholder organizations, broken local
  links and public version drift; its injected canary test passes.
- [x] Local npm network commands emitted a warning because the invoking shell
  externally set `NODE_TLS_REJECT_UNAUTHORIZED=0`. This variable is not stored
  in the repository; CI uses its default TLS verification.

## Checkpoint F: clean public candidate

- [x] Verified source commit: `7c56e47` (followed only by CI disclosure-parser
  correction `3b14ff0` before this evidence update).
- [x] Verified clean archive SHA-256:
  `82e1acdae502d6f3029c69428d6f7d761dfcde52430ed5715447f726236f8245`.
- [x] The archive contained 446 files and omitted `knowledge/`, `prompts/`,
  `content_scripts/`, `memory/`, restricted skill Markdown, databases, reports,
  `node_modules/`, local previews and every asset classified `exclude`.
- [x] Clean-archive Python result: 835 passed, 37 skipped, coverage 77.74%.
  Every skip is an explicit test for restricted corpus content that is not
  redistributed; the same tests run in the private tree when the corpus exists.
- [x] Clean-archive frontend result: 48 tests passed, production build passed,
  and moderate-level audit reported zero vulnerabilities.
- [x] Clean-archive container result: backend/frontend images built, health
  returned version 3.1.0 in demo mode, frontend returned HTTP 200, SQLite counts
  were `3|3|6`, and decoded SSE content included demo, synthetic and non-official
  disclosures. Containers and volumes were removed afterward.
- [x] Gitleaks v8.30.1 scanned 370 commits and found no leaks before the final
  test-only and CI-only corrections; the final release command is rerun before handoff.
- [ ] External publication remains intentionally blocked pending explicit user
  authorization for push, tag, GitHub Release or any other network mutation.
