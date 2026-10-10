# Final CI matrix

Recorded on 2026-10-10 against branch `fix/pre-demo-ci-remediation-v2`
(descendant of PR #5). The GitHub Actions run is linked under "CI run on GitHub
Actions"; the local commands and their output are listed per job below.

Every row below was executed on the machine that produced this document. Rows
that were not executed are marked `NOT VERIFIED` and are not claimed as passing.

## Readiness vocabulary

The four states are independent and must not be substituted for one another.

| State | Meaning in this project |
|---|---|
| `ENGINEERING_READY` | Functional CI is green: lint, tests, dependency audits, frontend build, container smoke. |
| `DEMO_READY` | The no-key community demo boots with synthetic data and honestly discloses its non-official status. |
| `DATA_QUALITY_READY` | A real database has been measured, duplicates classified, and the gaps documented. It does **not** mean the data may be published. |
| `PUBLIC_RELEASE_READY` | Functional gates **and** a recorded human compliance review (`release-evidence`). Blocked in this repository. |

Current status: **ENGINEERING_READY**, **DEMO_READY**, `DATA_QUALITY_READY` for the measured
local database only, **PUBLIC_RELEASE_BLOCKED**.

## Functional jobs (ENGINEERING_READY / DEMO_READY)

| Job | Command executed locally | Result | Evidence |
|---|---|---|---|
| Lint | `ruff check .` | PASS | `All checks passed!` |
| Format | `ruff format --check .` | PASS | `237 files already formatted` |
| Test (3.11) | `python -m pytest tests/ -q` | PASS | `910 passed, 38 skipped`, coverage `77.95%` (threshold 70%) |
| Test (3.10) | `python -m pytest tests/ -q` under CPython 3.10.12 | PASS | `910 passed, 38 skipped`, coverage `78.05%` |
| Security Audit | `pip-audit --strict --requirement requirements.lock` | PASS | `No known vulnerabilities found` |
| Lock consistency | `python scripts/check_lock_consistency.py` | PASS | `requirements.lock satisfies all 19 manifest requirement(s)` |
| Frontend install | `npm ci` | PASS | `added 219 packages ... found 0 vulnerabilities` |
| Frontend tests | `npm test -- --run` | PASS | `Test Files 8 passed`, `Tests 48 passed` |
| Frontend build | `npm run build` | PASS | `1833 modules transformed`, `built in 700ms` |
| Frontend audit | `npm audit --audit-level=moderate` | PASS | `found 0 vulnerabilities` |
| Data quality contract | `python scripts/data_quality_report.py --database /tmp/empty.db` | PASS (blocks) | empty DB exits `2` with `BLOCKED` |
| Data quality contract | demo DB after `scripts/seed_demo_data.py` | PASS | verdict `degraded`, exit `0`, no false block |
| Dedup dry run | `python scripts/dedupe_admission_scores.py --database /tmp/demo.db` | PASS | `DRY RUN — no rows were deleted` |
| Container smoke | `docker build` + run + health + SSE assertions | PASS | see "Container evidence" below |

## Release jobs (PUBLIC_RELEASE_READY)

| Job | Command executed locally | Result | Notes |
|---|---|---|---|
| Public docs | `python scripts/check_docs.py` | PASS | `11 files` |
| Dependency licenses | `python scripts/check_licenses.py` | PASS | no prohibited identifiers |
| Compose config | `docker compose config --quiet` | PASS | with `.env.example` |
| Repository audit | `bash scripts/audit_open_source.sh` | PASS | `failures=0 warnings=0` |
| Release-mode audit | `bash scripts/audit_open_source.sh --release` | PASS | no `exclude`-classified asset is tracked |
| Secret scan | gitleaks (containerised, staged candidate) | PASS | `no leaks found` |
| **Release evidence** | `python scripts/check_release_evidence.py` | **BLOCKED** | exit `1`; see `SECURITY_AND_LICENSE_BLOCKERS.md` |

`release-evidence` is expected to fail. It is the one gate that cannot be turned
green by engineering work; it requires a recorded human compliance review in
`config/compliance_attestation.yaml`. A red `release-evidence` job means
`PUBLIC_RELEASE_BLOCKED`, not a broken build.

## CI run on GitHub Actions

Local evidence is strong but not the same runner. The branch
`fix/pre-demo-ci-remediation` was pushed as a fast-forward of PR #5 and CI ran
on GitHub-hosted runners.

Run: <https://github.com/Xander-Xai/gaobao-advisor/actions/runs/38047310000>

| Job | Conclusion |
|---|---|
| Secret Scan (Git History) | success |
| Lint | success |
| Test (Python 3.10) | success |
| Test (Python 3.11) | success |
| Frontend Quality Gate | success |
| Security Audit | success |
| Data Quality Contract | success |
| No-key Container Smoke Test | success |
| Release Readiness (mechanical) | success |
| **Release Evidence (blocked until reviewed)** | **failure (by design)** |

The overall run is red solely because of `release-evidence`. That is the
expected and intended state: it means `PUBLIC_RELEASE_BLOCKED`, not a broken
build. Nine of ten jobs pass, which is the evidence for `ENGINEERING_READY` and
`DEMO_READY`.

### Container evidence

The container image was built and exercised twice: once locally and once by the
`No-key Container Smoke Test` job on GitHub Actions, which succeeded using the
networked PyPI path. The image is not left running after either run.

| Step | Result |
|---|---|
| `docker build -t gaobao-api:ci-test .` | PASS locally (host wheelhouse) and PASS in CI (official PyPI index) |
| `GET /api/v1/health` | `{"status":"ok","mode":"demo","llm_provider":"demo","optional_services":{"rag":"disabled","voice":"disabled"}}` |
| SSE `POST /api/v1/chat` disclosure | reply contains `演示模式`, `合成`, `非官方` |
| Data-grounded query inside the container | events `slots → emotion → structured → token… → quality → done` |

### Honest note on the local container build

This sandbox could not reach `files.pythonhosted.org` reliably, so the local
image was built from a wheelhouse downloaded by the host:

```bash
pip download -r requirements.lock -d wheels/ --only-binary=:all:
docker build -t gaobao-api:ci-test .
```

The Dockerfile selects that path automatically when `wheels/*.whl` exist and
falls back to the official PyPI index otherwise. Both paths are now verified:
the index path by the successful CI job above, the wheelhouse path locally.

## Things this matrix does not prove

- That the data may be published. `DATA_QUALITY_READY` says the data was
  measured; `PUBLIC_RELEASE_READY` additionally requires cleared rights.
- That `release-evidence` can pass. It cannot until a human records a review.

## Reproducing

```bash
# functional
ruff check . && ruff format --check .
python -m pytest tests/ -q
pip-audit --strict --requirement requirements.lock
python scripts/check_lock_consistency.py
(cd frontend && npm ci && npm test -- --run && npm run build && npm audit --audit-level=moderate)

# data contract
python scripts/seed_demo_data.py --database /tmp/demo.db
python scripts/data_quality_report.py --database /tmp/demo.db
python scripts/dedupe_admission_scores.py --database /tmp/demo.db

# release
python scripts/check_docs.py
python scripts/check_licenses.py
bash scripts/audit_open_source.sh --release
python scripts/check_release_evidence.py   # expected to fail
```
