# Phase 1 — 高优先级修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 high-priority audit items: CSP unsafe-inline, delete deprecated app.py, fix scripts/ ruff errors, and add Sentry monitoring.

**Architecture:** Four independent tasks with no cross-dependencies. Tasks 1-3 can be done in parallel. Task 4 (Sentry) requires adding a dependency. Total estimated time: ~1 hour.

**Tech Stack:** nginx, Python 3.11+, FastAPI, Sentry SDK, ruff

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `nginx.conf:20` | Remove `'unsafe-inline'` from script-src |
| Delete | `app.py` | Remove deprecated Streamlit entry point |
| Modify | `scripts/check_db_stats.py:3,46-51` | Fix E401/E701 |
| Modify | `scripts/check_db_real.py:3,73-77,79` | Fix E401/E701/W292 |
| Create | `server/monitoring.py` | New Sentry init module |
| Modify | `requirements.txt` | Add `sentry-sdk` |
| Modify | `requirements.lock` | Recompile |
| Modify | `server/main.py:1-20` | Add Sentry init call |

---

### Task 1: Fix CSP — remove unsafe-inline from script-src

**Files:**
- Modify: `nginx.conf:20`

- [ ] **Step 1: Update CSP header**

Change line 20 from:
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;" always;
```
to:
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:;" always;
```

Rationale: The React frontend (CRA) outputs fingerprinted script bundles — no inline scripts needed. `style-src 'unsafe-inline'` is retained because CRA injects inline styles for critical CSS. The `script-src` `'unsafe-inline'` removal is the most impactful security improvement.

- [ ] **Step 2: Verify syntax**

Run: `nginx -t -c /home/dev/projects/gaobao/gaobao-advisor/nginx.conf`
Expected: `syntax is ok` (or skip if nginx not installed locally; syntax is standard)

- [ ] **Step 3: Commit**

```bash
git add nginx.conf
git commit -m "security: remove 'unsafe-inline' from script-src in CSP header (P1-audit)"
```

---

### Task 2: Delete deprecated app.py

**Files:**
- Delete: `app.py`

- [ ] **Step 1: Verify app.py is safe to delete**

Check that no entry points reference `app.py`:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
grep -r "app.py" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.md" --include="*.toml" --include="*.cfg" --include="*.ini" --include="Dockerfile"
```
Expected: Only docker-compose.yml streamlit services section and docs references. The FastAPI entry point is `server/main.py`.

- [ ] **Step 2: Verify docker-compose.yml streamlit service can still exist without app.py**

The docker-compose.yml streamlit service (line 39-51) references `app.py` in its command. Since it's behind `profiles: ["legacy"]`, it only runs when explicitly invoked. When Phase 2 cleans up the docker-compose.yml, this will be resolved. For now, the reference is a comment-only doc — no runtime impact.

- [ ] **Step 3: Delete app.py**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
rm app.py
```

- [ ] **Step 4: Verify ruff no longer has false positives**

Run: `ruff check . --exclude '.claude' --exclude 'scripts' --exclude 'frontend' --exclude 'node_modules' --exclude '__pycache__' --exclude 'data'`
Expected: 0 errors (was 9 E402 in app.py previously)

- [ ] **Step 5: Commit**

```bash
git rm app.py
git commit -m "chore: remove deprecated app.py (P1-audit)"
```

---

### Task 3: Fix scripts/ ruff errors

**Files:**
- Modify: `scripts/check_db_stats.py`
- Modify: `scripts/check_db_real.py`

- [ ] **Step 1: Auto-fix what ruff can fix**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
ruff check scripts/ --exclude '__pycache__' --fix
```
Expected: 6 fixable errors auto-repaired (E401×2, I001×3, W292×1).

- [ ] **Step 2: Manually fix remaining 8 E701 errors**

All E701 errors follow the same pattern — `if cond: var = val` on one line. Fix by expanding to multi-line.

**File: `scripts/check_db_stats.py:47-50`**

Change:
```python
for r in c.fetchall():
    if r[0] == 1: label = 'L1 双一流'
    elif r[1] == 1: label = 'L2 省属重点'
    elif r[2] == 1: label = 'L4 专科'
    else: label = 'L3 一般本科'
    print(f'{label}: {r[3]} 校, {r[4]} 有数据 ({r[4]*100//r[3]}%)')
```
to:
```python
for r in c.fetchall():
    if r[0] == 1:
        label = 'L1 双一流'
    elif r[1] == 1:
        label = 'L2 省属重点'
    elif r[2] == 1:
        label = 'L4 专科'
    else:
        label = 'L3 一般本科'
    print(f'{label}: {r[3]} 校, {r[4]} 有数据 ({r[4]*100//r[3]}%)')
```

**File: `scripts/check_db_real.py:73-77`**

Change:
```python
for r in c.fetchall():
    if r[0] == 1: label = 'L1 双一流'
    elif r[1] == 1: label = 'L2 省属重点'
    elif r[2] == 1: label = 'L4 专科'
    else: label = 'L3 一般本科'
    print(f'{label}: {r[3]} 校, {r[4]} 有2025数据 ({r[4]*100//r[3]}%)')
```
to:
```python
for r in c.fetchall():
    if r[0] == 1:
        label = 'L1 双一流'
    elif r[1] == 1:
        label = 'L2 省属重点'
    elif r[2] == 1:
        label = 'L4 专科'
    else:
        label = 'L3 一般本科'
    print(f'{label}: {r[3]} 校, {r[4]} 有2025数据 ({r[4]*100//r[3]}%)')
```

- [ ] **Step 3: Verify clean ruff**

Run: `ruff check scripts/ --exclude '__pycache__'`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add scripts/check_db_stats.py scripts/check_db_real.py
git commit -m "chore: fix ruff errors in scripts/ (E401, E701, W292) (P1-audit)"
```

---

### Task 4: Add Sentry monitoring

**Files:**
- Create: `server/monitoring.py`
- Modify: `requirements.txt`
- Modify: `server/main.py`

- [ ] **Step 1: Create server/monitoring.py**

Create `server/monitoring.py`:
```python
"""Application monitoring — Sentry integration for error tracking.

Usage:
    from server.monitoring import init_sentry
    init_sentry()  # call at startup
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN environment variable is set.

    Integrates with FastAPI and SQLAlchemy automatically.
    Safe to call even when SENTRY_DSN is not configured — no-op in that case.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("SENTRY_DSN not set — Sentry monitoring disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("APP_ENV", "development"),
            release=os.getenv("APP_VERSION", "unknown"),
        )
        logger.info("Sentry monitoring initialized (env=%s)", os.getenv("APP_ENV", "development"))
    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry monitoring unavailable")
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", e)
```

- [ ] **Step 2: Add sentry-sdk to requirements.txt**

Append to `requirements.txt`:
```
# ── Monitoring ──
sentry-sdk>=2.0.0,<3.0.0
```

- [ ] **Step 3: Wire init_sentry into main.py startup**

Add import and call in `server/main.py`. After the existing imports (around line 18), add:
```python
from server.monitoring import init_sentry
```

Inside the `lifespan` function, before `init_db()`:
```python
init_sentry()
```

The resulting lifespan function should look like:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_sentry()

    from db.database import init_db
    init_db()
    # ... rest unchanged
```

- [ ] **Step 4: Verify import and ruff**

Run: `python3 -c "from server.monitoring import init_sentry; print('import OK')"`
Expected: `import OK`

Run: `ruff check server/monitoring.py`
Expected: 0 errors

Run: `ruff check server/main.py`
Expected: 0 errors

- [ ] **Step 5: Run existing tests**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python3 -m pytest tests/test_server_health.py -v 2>&1 | tail -10`
Expected: tests pass

- [ ] **Step 6: Recompile requirements.lock**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
uv pip compile requirements.txt -o requirements.lock 2>&1 | tail -5
```
Expected: lock file updated with sentry-sdk and its dependencies

- [ ] **Step 7: Commit**

```bash
git add server/monitoring.py server/main.py requirements.txt requirements.lock
git commit -m "feat: add Sentry monitoring with init_sentry() (P1-audit)"
```

---

## Phase 1 Verification (all tasks complete)

- [ ] `ruff check nginx.conf` — N/A (not a Python file). Verify manually: the CSP line has no `'unsafe-inline'` in script-src.

- [ ] `ruff check . --exclude '.claude' --exclude 'scripts' --exclude 'frontend' --exclude 'node_modules' --exclude '__pycache__' --exclude 'data'`
      Expected: 0 errors

- [ ] `ruff check scripts/ --exclude '__pycache__'`
      Expected: 0 errors

- [ ] `python3 -c "from server.monitoring import init_sentry; print('✅ Sentry module OK')"`
      Expected: ✅

- [ ] `python3 -m pytest tests/test_server_health.py -v 2>&1 | tail -5`
      Expected: PASSED

- [ ] `ls app.py 2>&1; echo "exit=$?"`
      Expected: `ls: cannot access 'app.py': No such file or directory` + `exit=2`
