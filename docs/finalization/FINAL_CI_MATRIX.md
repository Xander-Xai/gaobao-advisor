# Final CI matrix

Recorded on 2026-10-10 against branch `fix/pre-demo-ci-remediation-v2`
(descendant of PR #5) at the commit described at the bottom of this file.

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
| Test (3.11) | `python -m pytest tests/ -q` | PASS | `910 passed, 38 skipped`, coverage `78.28%` (threshold 70%) |
| Test (3.10) | `python -m pytest tests/ -q` under CPython 3.10.12 | PASS | `910 passed, 38 skipped`, coverage `78.37%` |
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

## Container evidence

The container image was built and exercised, then removed.

| Step | Result |
|---|---|
| `docker build -t gaobao-api:ci-test .` | PASS, using a host-built wheelhouse (`pip download -r requirements.lock`) |
| `GET /api/v1/health` | `{"status":"ok","mode":"demo","llm_provider":"demo","optional_services":{"rag":"disabled","voice":"disabled"}}` |
| SSE `POST /api/v1/chat` disclosure | reply contains `演示模式`, `合成`, `非官方` |
| Data-grounded query inside the container | events `slots → emotion → structured → token… → quality → done` |

### Honest limitation on the container build

The Docker build in this environment could not reach `files.pythonhosted.org`
reliably, so the image was built from a wheelhouse downloaded by the host:

```bash
pip download -r requirements.lock -d wheels/ --only-binary=:all:
docker build -t gaobao-api:ci-test .
```

The Dockerfile selects that path automatically when `wheels/*.whl` exist and
falls back to the official PyPI index otherwise. The index fallback (the path CI
uses) was verified only at the branch-selection level, not by a full networked
build. On a GitHub-hosted runner with normal PyPI connectivity the index path is
expected to succeed; it is the same `pip install` invocation that produces the
local environment.

## Things this matrix does not prove

- That CI itself passes on GitHub Actions. Local execution is strong evidence but
  not the same runner. The first CI run on the pushed branch is the authority.
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
