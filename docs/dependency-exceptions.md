# Dependency security record

This file is the auditable record of the runtime dependency policy of this
repository and of every known exception to it.

It is **not** a list of "things we would like to fix". Every entry states who
decided it, why, and what would close it.

---

## 1. Policy

| Set | File | What it is | Rule |
|---|---|---|---|
| **Runtime** | `requirements.txt` → `requirements.lock` | what the Docker image installs and what the public demo runs | **zero known vulnerabilities** — `pip-audit` must report "No known vulnerabilities found" |
| **Reviewed pins** | `requirements.lock.constraints` | the exact versions of the runtime set that were installed, tested and audited | changes only on purpose, never by a plain re-resolve |
| **Optional / legacy** | `requirements-legacy-admin.txt` → `requirements-legacy-admin.lock` | the local operator dashboard (`legacy/admin.py`), which needs Streamlit | not shipped, not installed by `pip install -e .`; audited separately. E-001 is closed (pillow 13.0.0), so the audit has no ignore list. |

Regenerate the runtime lock with:

```bash
make lock        # uv pip compile requirements.txt -o requirements.lock \
                 #     --constraint requirements.lock.constraints
```

A plain `uv pip compile requirements.txt -o requirements.lock` (without the
constraints file) floats **54 packages** — `fastapi`, `starlette`, `sqlalchemy`,
`langchain-core`, `openai` and so on. That is a platform upgrade, not a
security fix, and it must not ride along behind a CVE reference. Use the
constraints file, change a pin there deliberately, and re-run the audit and the
tests.

---

## 2. 2026-10-21 — runtime set brought to zero known vulnerabilities

**Trigger.** `pip-audit` failed on `requirements.lock` with 9 advisories in 2
packages. The advisories were published after the last green `master` run, so
`master` failed the same gate before this change.

| Package | Before | Advisory | Fix | Action |
|---|---|---|---|---|
| `certifi` | 2026.5.20 | `PYSEC-2026-4320` — the release bundles an eSign root CA whose intermediate keys are compromised | 2026.10.19 | **bumped** (patch-level, `requests` only requires `certifi>=2023.5.7`) |
| `pillow` | 12.3.0 | `CVE-2026-112395`, `-112397`, `-112400`, `-112404`, `-112895`, `-112896`, `-112897`, `-112899` | 13.0.0 | **removed from the runtime set** (see below) |

### Why `pillow` was removed rather than upgraded

`pillow` was in the runtime set only through two dependencies, and neither one
is needed by the shipped code:

* `reportlab>=4.0` — **no module in this repository imports reportlab.** The
  report export renders HTML + SVG (`server/report/exporter.py`), not PDF. The
  dependency was simply unused.
* `streamlit>=1.30.0` — used only by the legacy operator dashboard
  (`legacy/admin.py`). It is not part of the API, the container or CI.

Upgrading `pillow` to 13.0.0 was not possible while either was present:

* every released Streamlit from 1.51.0 to 1.66.0 pins `pillow<13`;
* `pillow` 13.0.0 declares `requires_python >= 3.11`, so it cannot be
  installed on Python 3.10 at all.

Removing both dependencies removes `pillow` from the runtime set entirely, so
the runtime has **no** `pillow` rather than a "recent" `pillow`. That also
keeps the lock installable on the whole supported Python range.

### Result

`pip-audit --requirement requirements.lock` → **"No known vulnerabilities found"**.

### Verified impact

| Check | Result |
|---|---|
| Runtime lock diff | 25 packages removed, 0 added, 1 version changed (`certifi`) — every other pin byte-identical |
| Fresh install of the new lock | installs cleanly; `streamlit`/`pillow`/`reportlab` absent |
| `pip-audit` (CI-equivalent, full resolution) | No known vulnerabilities found |
| Test suite in a clean venv **without** streamlit/pillow/reportlab | 999 passed, 1 skipped, coverage 80.69% |
| API health with the new lock | `status: ok`, `data_profile: SYNTHETIC_DEMO`, RAG `RAG_ENABLED` (8 documents / 31 chunks / `integrity_ok: true`) |
| No-key RAG | `has_evidence: true`, 4 chunks, 2 citations |
| Chat SSE | 200 `text/event-stream`, events `emotion → structured → sources → degraded → token×7 → done`; session id server-issued, caller-supplied id ignored |
| Docker build + no-key container smoke | health / schools / RAG-evidence checks all pass |
| Image `site-packages` | 766 MB → 428 MB (−338 MB, −44%) |

### Removed packages (25)

`altair`, `blinker`, `cachetools`, `gitdb`, `gitpython`, `itsdangerous`,
`jinja2`, `jsonschema`, `jsonschema-specifications`, `markupsafe`, `narwhals`,
`pandas`, `pillow`, `protobuf`, `pyarrow`, `pydeck`, `python-dateutil`,
`referencing`, `reportlab`, `rpds-py`, `six`, `smmap`, `streamlit`, `toml`,
`watchdog`.

---

## 3. Exception register

### E-001 — `pillow` in the optional legacy admin dependency set — **CLOSED 2026-10-31**

| Field | Value |
|---|---|
| Scope | `requirements-legacy-admin.lock` only. **Not** in `requirements.lock`, **not** in the image, **not** in CI's test job. |
| Before | `pillow` 12.3.0 (pulled in by `streamlit==1.66.0`, which pinned `pillow<13`) |
| Resolution | `streamlit==1.66.1` permits `pillow<14`; the legacy lock now pins **`pillow==13.0.0`**. |
| Advisories closed | `CVE-2026-112395`, `-112397`, `-112400`, `-112404`, `-112895`, `-112896`, `-112897`, `-112899`, plus the later Pillow 12.3.0 advisories reported by `pip-audit` (31 total, fix version 13.0.0). |
| Enforcement | CI audits `requirements-legacy-admin.lock` with **no ignore list**. Any advisory fails the build. |
| Python floor | Pillow 13 requires Python ≥ 3.11; the legacy operator set therefore needs Python 3.11+. The runtime/test matrix is unchanged. |
| Owner | repository maintainer |

The legacy set remains optional and is not installed by default or shipped in
the image. `streamlit==1.66.1` is the only lock change; all other legacy pins
are unchanged.

---

## 4. Open decisions (not decided here)

### D-1 — keep or delete the legacy Streamlit dashboard

`legacy/admin.py` (operations dashboard) and the Streamlit renderers in
`legacy/onboarding.py` are the only remaining users of Streamlit. The
dashboard reads `data/analytics.db` and `data/gaokao.db`, neither of which the
public demo creates — it generates `data/demo.db` — so in this repository it
has no data source and shows an empty dashboard.

* **Option A — keep it** (what this change does): the capability stays, isolated
  in `requirements-legacy-admin.txt`, with exception `E-001` recorded above.
* **Option B — delete it**: remove `legacy/admin.py`, the Streamlit renderers in
  `legacy/onboarding.py` and `.streamlit/`, and drop `requirements-legacy-admin.*`.
  This closes `E-001` with no exception record at all.

Option B removes a local operator capability, so it is a product decision and is
**not** taken by this change.

### D-2 — Python 3.10 support

`pillow` 13.0.0 requires Python ≥ 3.11. The **legacy admin** set now requires
Python 3.11+; the runtime and test matrix are unchanged. `pyproject.toml` still
declares `requires-python = ">=3.10"`, and CI still tests 3.10 and 3.11 from
`pyproject.toml`, not from the lock.

If the maintainer wants the legacy lock usable on Python 3.10, that is a
separate decision with its own compatibility check.
