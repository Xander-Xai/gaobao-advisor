# Resume claims

Each claim is matched to evidence that can be checked in the repository and a
command that reproduces it. Claims marked **do not claim** must not appear on a
resume or in an interview until the underlying condition changes.

## Status line

> `ENGINEERING_READY` · `DEMO_READY` · `DATA_QUALITY_READY` (measured locally) ·
> `PUBLIC_RELEASE_BLOCKED` (compliance review outstanding)

## Claims that are supported

| # | Claim | Evidence | Reproduce |
|---|---|---|---|
| 1 | Built an AI college-application advisor as a 13-node LangGraph pipeline (security → intent → slots → profile → data → hybrid RAG → reasoning → structured card → source attribution → quality → memory). | `server/graph/graph.py` | `python -m pytest tests/test_business_smoke.py -q` |
| 2 | Enforced a provenance rule so no score reaches the user without a source or year; unverifiable records are downgraded and labelled. | `server/services/data_query.py::annotate_provenance`, `server/graph/nodes/source_attribution.py` | `python -m pytest tests/test_data_provenance.py tests/test_source_attribution.py -q` |
| 3 | Implemented a hybrid RAG layer (dense + keyword) with an optional Redis cache that degrades to in-memory. | `server/services/rag.py`, `server/services/rag_cache.py`, `server/services/kb_retriever.py` | `python -m pytest tests/test_rag_cache.py tests/test_kb_retriever.py -q` |
| 4 | Shipped a no-key community demo that runs on explicitly synthetic data and discloses its non-official status in every reply. | `docker-compose.yml`, `scripts/seed_demo_data.py`, `server/routes/chat.py` | `python -m pytest tests/test_demo_seed.py tests/test_business_smoke.py -q` |
| 5 | Wrote a data-quality tool that measures coverage, freshness, completeness and duplicate classes, and blocks on an empty or unreadable database instead of reporting a false pass. | `scripts/data_quality_report.py` | `python scripts/data_quality_report.py --database data/gaokao.db` |
| 6 | Measured a real 380,671-row admissions dataset, found 3,429 lossless duplicates and 559 business-key conflict groups, and wrote a tiered dedup plan that refuses to delete the conflicting tier. | `scripts/dedupe_admission_scores.py` | `python scripts/dedupe_admission_scores.py --database data/gaokao.db` |
| 7 | Corrected a backup pipeline that produced `gzip → sqlite` files named `.sql.gz`; built format detection by magic bytes and a restore command that is dry-run by default, snapshots before writing and refuses to overwrite. | `scripts/db_archive.py`, `scripts/restore_db.py` | `python -m pytest tests/test_db_archive.py -q` |
| 8 | Added end-to-end business smoke tests covering missing profile, empty results, stale data, incomplete records, prompt injection, provider outage, session isolation and runtime-mode differences. | `tests/test_business_smoke.py` | `python -m pytest tests/test_business_smoke.py -q` |
| 9 | Hardened prompt-injection detection for credential exfiltration and closed a Chinese-language, case-sensitivity gap, with false-positive guards. | `server/middleware/security.py` | `python -m pytest tests/test_middleware_security.py -q` |
| 10 | Restructured CI into functional gates and release gates, and made the compliance gate fail until a human records a review — no skipped compliance check. | `.github/workflows/ci.yml`, `scripts/check_release_evidence.py` | `python scripts/check_release_evidence.py` |
| 11 | Fixed a broken `npm ci` (lock and manifest drift that dropped a dependency) and cleared npm and pip advisories to zero. | `frontend/package-lock.json`, `requirements.lock` | `(cd frontend && npm ci && npm audit --audit-level=moderate) && pip-audit --strict -r requirements.lock` |
| 12 | Kept the full test suite green on both CI Python versions. | `tests/` | `python -m pytest tests/ -q` → `910 passed, 38 skipped`, coverage `78.3%` (3.10 and 3.11) |

## Numbers you may quote (measured 2026-10-10)

- `910 passed, 38 skipped`, coverage `77.95%` (3.11) / `78.05%` (3.10), and CI-verified.
- `frontend`: 48 tests passing, 0 npm vulnerabilities, production build succeeds.
- `pip-audit --strict`: no known vulnerabilities.
- Data: 3,020 schools, 215 majors, 380,671 admission rows, 96.3% school coverage,
  90.2% major coverage, years 2022–2025.
- Duplicates: 3,429 lossless, 559 conflicting groups.
- 13-node LangGraph pipeline; 3,000+ lines of Python across `server/`, `slots/`,
  `db/`, `quality/`, `analytics/`.

Quote these only after re-running the corresponding command. Numbers drift.

## Do not claim

| Don't claim | Why |
|---|---|
| "Production ready" / "released" | `PUBLIC_RELEASE_BLOCKED`. No compliance review on record. |
| "Legally compliant" / "GDPR/《个保法》 compliant" | No legal review was performed. `PRIVACY.md` and `DATA_LICENSE.md` are marked draft. |
| "The dataset is complete / authoritative" | Measured as incomplete: 112 schools with no data, 251,238 rows with no major, one placeholder province bucket. |
| "Zero duplicates" | 3,429 byte-identical rows remain in the working database; the conflicting 559 groups are unresolved by design. |
| "99%+ uptime" / "serves N users" | No production telemetry exists. |
| "Fully migrated off Streamlit" | `streamlit` remains in `requirements.txt`; the legacy UI is not started by any compose service. |
| "The public repo contains no private data" | The Git history on `master` still contains the database archives. This is listed as blocker B1. |

The container build **is** verified in CI (`No-key Container Smoke Test` passes
on GitHub Actions), so it is safe to say the image builds and boots. Do not
claim production uptime or scale from that.

## Longer-form bullets (for a project section)

- **AI application engineering:** designed and implemented a 13-node LangGraph
  advisor with explicit control flow for incomplete profiles, a post-generation
  quality loop, and a source-attribution stage that gates every numeric claim.
- **Data engineering:** measured and documented a 380k-row admissions dataset;
  built a tiered, reversible deduplication planner and a format-agnostic,
  dry-run-by-default backup/restore toolchain that caught a mislabelled
  `gzip → sqlite` backup convention and a self-inflicted destructive-SQL bug
  before it ran.
- **Release engineering:** split CI into functional and release gates; introduced
  a machine-readable compliance attestation so legal/data-readiness cannot be
  faked green; fixed a broken `npm ci` and drove pip and npm advisories to zero.
- **Security:** added credential-exfiltration detection with false-positive
  tests; maintained session-token isolation, CSP, and output sanitisation.
- **Quality discipline:** 910 automated tests across Python 3.10/3.11, plus a
  business smoke suite that exercises the full path the product promises.
