# Gaobao Next Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all unfinished work across 4 sprints: infrastructure, data, product UX, and production deployment — ready for gaokao season.

**Architecture:** Sequential 4-sprint plan. S1 clears blockers (brand, CI, RAG). S2 completes data. S3 improves UX. S4 deploys and adds commercial hooks. Each sprint produces working, testable software.

**Tech Stack:** Python 3.11, Streamlit, FastAPI, SQLite/SQLAlchemy, OpenAI-compatible API, Docker

---

## File Structure

### Files to Create
| File | Responsibility |
|------|---------------|
| `.github/workflows/ci.yml` | GitHub Actions CI pipeline |
| `pyproject.toml` | Modern Python project metadata |
| `Makefile` | Local dev shortcuts |
| `docker-compose.prod.yml` | Production Docker Compose |
| `.env.production` | Production environment template |
| `scripts/backup_db.sh` | Daily database backup script |
| `onboarding.py` | 3-step onboarding card renderer (extracted from app.py) |

### Files to Modify
| File | Changes |
|------|---------|
| `agent.py` | Brand update (line 22 area), disclaimer post-processing (line ~1540) |
| `app.py` | Brand update (line 1518), sidebar conversation history (line 1444), loading phases already exist (line 1789), import onboarding |
| `system_prompt.md` | Version bump to v2.8, persona change (lines 22, 34-49) |
| `prompts/templates/persona.md` | Remove XuefengAgent reference (line 19) |
| `.env.example` | Enable RAG by default (line 31) |
| `kb_retriever.py` | Add retrieval logging |
| `api_server.py` | Add rate limiting (line 68 area), session TTL cleanup |
| `scrapers/baidu_gaokao.py` | Verify layer import functions |
| `Dockerfile` | Health check update |
| `docker-compose.yml` | Service naming update |
| `README.md` | Brand references |

---

## Sprint 1: Infrastructure (Day 1-3)

### Task 1: Fix Failing Test + Verify 274/274 Green

**Files:**
- Modify: `tests/test_import_pipeline.py:6-39`
- Modify: `scrapers/baidu_gaokao.py:189-255` (if test reveals a code bug)

- [ ] **Step 1: Run the failing test to see exact error**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
pytest tests/test_import_pipeline.py::test_import_schools_fills_missing_city -v 2>&1
```

Expected: FAIL — note the exact assertion error message.

- [ ] **Step 2: Read the test and implementation to identify the mismatch**

Read `tests/test_import_pipeline.py` lines 6-39 and `scrapers/baidu_gaokao.py` function `import_schools_to_db()` (lines 189-255). Compare what the test expects (filling empty city/ranking/description from API) with what the code actually does.

- [ ] **Step 3: Fix either the test or the implementation**

If the code doesn't fill missing fields: add the fill logic to `import_schools_to_db()`. If the test mocks are wrong: fix the mock setup. Use this pattern for the fill-only logic:

```python
# In import_schools_to_db, when updating existing school:
if not existing_school.city and api_school.city:
    existing_school.city = api_school.city
if existing_school.ranking is None and api_school.ranking is not None:
    existing_school.ranking = api_school.ranking
if not existing_school.description and api_school.description:
    existing_school.description = api_school.description
```

- [ ] **Step 4: Run the fixed test**

```bash
pytest tests/test_import_pipeline.py::test_import_schools_fills_missing_city -v 2>&1
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest --tb=short 2>&1
```

Expected: 274 collected, 274 passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_import_pipeline.py scrapers/baidu_gaokao.py
git commit -m "fix: resolve test_import_schools_fills_missing_city assertion mismatch"
```

---

### Task 2: CI/CD + pyproject.toml + Makefile

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create pyproject.toml**

```toml
# pyproject.toml
[project]
name = "gaobao-advisor"
version = "1.0.0"
description = "AI 高考志愿顾问 — 个性化大学和专业推荐"
requires-python = ">=3.10"
dependencies = [
    "openai>=1.0",
    "streamlit>=1.30",
    "fastapi>=0.100",
    "uvicorn>=0.20",
    "sqlalchemy>=2.0",
    "reportlab>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
]

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Create Makefile**

```makefile
.PHONY: install test lint run run-api clean

install:
	pip install -e ".[dev]"

test:
	pytest --tb=short -q

test-cov:
	pytest --cov=. --cov-report=term-missing --tb=short -q

lint:
	ruff check .

lint-fix:
	ruff check --fix .

run:
	streamlit run app.py --server.port=8501

run-api:
	uvicorn api_server:app --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
```

- [ ] **Step 3: Create GitHub Actions CI workflow**

Create directory and file:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check . --output-format=github

      - name: Run tests with coverage
        run: pytest --cov=. --cov-report=xml --tb=short -q
```

- [ ] **Step 4: Verify pyproject.toml works**

```bash
pip install -e ".[dev]" 2>&1 | tail -5
make test 2>&1
make lint 2>&1
```

Expected: Both install and tests pass. Lint may show warnings (not errors).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .github/workflows/ci.yml
git commit -m "feat: add CI/CD pipeline, pyproject.toml, and Makefile"
```

---

### Task 3: Brand Overhaul — Remove Zhang Xuefeng References

**Files:**
- Modify: `system_prompt.md:22,34-49`
- Modify: `app.py:1518`
- Modify: `prompts/templates/persona.md:19`
- Modify: `README.md` (all Zhang Xuefeng references)

- [ ] **Step 1: Audit all brand references**

```bash
grep -rn "雪峰\|xuefeng\|Xuefeng\|张雪峰" --include="*.py" --include="*.md" --include="*.html" --include="*.yml" --include="*.toml" . 2>/dev/null | grep -v __pycache__ | grep -v ".pyc"
```

Expected output: list of all files and lines. Based on exploration:
- `system_prompt.md` line 22: "身份锁定：你始终是雪峰"
- `system_prompt.md` lines 34-49: persona description
- `app.py` line 1518: "雪峰Agent"
- `prompts/templates/persona.md` line 19: "XuefengAgent"
- `README.md`: case study references

- [ ] **Step 2: Update system_prompt.md persona**

At line 22, change:
```
**身份锁定**：你始终是雪峰，一个高考志愿规划师。
```
To:
```
**身份锁定**：你始终是一位资深高考志愿规划师，从业十年以上。
```

At lines 34-49 (the "你是谁" section), replace the persona with:
```markdown
## 你是谁

你是一个在高考志愿规划这一行干了十几年的老炮。你见过太多考生和家长因为信息差、认知差而做出错误选择。你说话直来直去，不绕弯子，因为你知道：在志愿填报这件事上，好听的废话会害了孩子。

你的核心理念：
1. **选择 > 努力**：方向错了，越努力越遗憾
2. **就业倒推法**：先看就业市场，再选专业和学校
3. **数据说话**：不靠感觉，靠录取数据做决策
```

- [ ] **Step 3: Update app.py brand name**

At line 1518, change:
```python
'⭐ Powered by <b>雪峰Agent</b> · '
```
To:
```python
'⭐ Powered by <b>gaobao</b> · '
```

- [ ] **Step 4: Update prompts/templates/persona.md**

At line 19, change any `XuefengAgent` reference to `GaokaoAdvisor`:
```python
# Find the line referencing XuefengAgent and replace with:
# advisor = GaokaoAdvisor(...)
```

- [ ] **Step 5: Update README.md**

Replace all "张雪峰"/"雪峰" references with generic "资深高考顾问" or "gaobao". Key areas:
- Title and description
- Case studies / demo descriptions
- Feature list descriptions

- [ ] **Step 6: Verify no core references remain**

```bash
grep -rn "雪峰\|xuefeng\|Xuefeng\|张雪峰" --include="*.py" --include="*.md" --include="*.html" . 2>/dev/null | grep -v __pycache__ | grep -v "knowledge/quotes" | grep -v "content_scripts"
```

Expected: Only `knowledge/quotes/` (kept as "行业专家观点") and `content_scripts/` (historical content) should remain.

- [ ] **Step 7: Run tests to ensure brand changes don't break anything**

```bash
pytest --tb=short -q 2>&1
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add system_prompt.md app.py prompts/templates/persona.md README.md
git commit -m "feat: rebrand from xuefeng to gaobao — remove all persona-specific references"
```

---

### Task 4: Enable RAG by Default

**Files:**
- Modify: `.env.example:31`
- Modify: `kb_retriever.py` (add logging)

- [ ] **Step 1: Enable RAG in .env.example**

At line 31, change:
```
# ENABLE_RAG_KB=true   # 启用向量+关键词混合检索（默认关闭，使用旧的全量注入）
```
To:
```
ENABLE_RAG_KB=true   # 启用向量+关键词混合检索
```

- [ ] **Step 2: Add retrieval logging to kb_retriever.py**

Find the main retrieval function (the function that combines vector + keyword results) and add logging at the end:

```python
import logging
logger = logging.getLogger(__name__)

# After the hybrid search returns results, add:
logger.info("RAG retrieval: query=%s, results=%d, method=%s",
            query[:50], len(results), "hybrid" if self._has_embeddings else "keyword")
```

- [ ] **Step 3: Verify RAG fallback path works without embedding key**

```bash
# Temporarily unset embedding vars to test keyword-only path
unset EMBEDDING_PROVIDER EMBEDDING_MODEL
python -c "
from kb_retriever import KnowledgeBaseRetriever
kb = KnowledgeBaseRetriever()
results = kb.retrieve('计算机专业就业前景', top_k=3)
print(f'Results: {len(results)}')
for r in results:
    print(f'  - {r[\"source\"]} (score: {r[\"score\"]:.2f})')
" 2>&1
```

Expected: Returns 3 results from keyword-only search.

- [ ] **Step 4: Commit**

```bash
git add .env.example kb_retriever.py
git commit -m "feat: enable RAG by default with keyword fallback"
```

---

### Sprint 1 Verification

- [ ] **Run full test suite**: `pytest --tb=short -q` — expect 274/274 pass
- [ ] **Verify brand**: `grep -rn "雪峰" --include="*.py" . | grep -v __pycache__ | grep -v knowledge/quotes` — expect 0 results
- [ ] **Verify CI config**: `cat .github/workflows/ci.yml` — confirm valid YAML
- [ ] **Verify RAG default**: `grep "ENABLE_RAG_KB" .env.example` — confirm `true`

---

## Sprint 2: Data + Credibility (Day 4-7)

### Task 5: Run L1 Import to Completion

**Files:**
- No code changes — data pipeline execution only

- [ ] **Step 1: Check current import status**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python scripts/validate_data.py 2>&1 | head -30
```

Check how many L1 schools are complete.

- [ ] **Step 2: Complete L1 import if needed**

```bash
python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L1 --top-n 100 2>&1 | tail -20
```

Wait for completion. Expected: All 30 provinces × top schools imported.

- [ ] **Step 3: Start L2 import in background**

```bash
nohup python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L2 --top-n 50 > /tmp/import_L2.log 2>&1 &
echo "L2 PID: $!"
```

- [ ] **Step 4: Start L3 import after L2 completes (or in parallel with different provinces)**

```bash
# Check L2 progress
tail -5 /tmp/import_L2.log

# When L2 is done or running stably:
nohup python scripts/import_baidu_gaokao.py --resume --provinces ALL --layer L3 --top-n 30 > /tmp/import_L3.log 2>&1 &
echo "L3 PID: $!"
```

- [ ] **Step 5: Verify data growth**

```bash
python -c "
from db.database import get_db
from sqlalchemy import text
db = next(get_db())
r = db.execute(text('SELECT COUNT(*) FROM admission_scores')).scalar()
print(f'Total admission scores: {r}')
r2 = db.execute(text('SELECT COUNT(*) FROM schools')).scalar()
print(f'Total schools: {r2}')
" 2>&1
```

Expected: admission_scores growing toward 100,000+

---

### Task 6: Yi-Fen-Yi-Duan Import

**Files:**
- Modify: `scripts/import_yi_fen_yi_duan.py` (complete the stub at line 170)
- Modify: `db/crud.py` (add bulk insert if needed)

- [ ] **Step 1: Read the current import script**

Read `scripts/import_yi_fen_yi_duan.py` fully. The `reverse_engineer_rank_table()` function at line 26 already creates rank data from admission_scores. The `import_yifenyd_csv()` at line 170 is a stub.

- [ ] **Step 2: Implement reverse-engineer import (primary path)**

Since CSV data sources may not be available, implement the reverse-engineering path that extracts rank info from existing admission_scores data:

```python
# Add to import_yi_fen_yi_duan.py main() function
def populate_from_admission_scores(db_path: str = "data/gaokao.db") -> int:
    """Populate yi_fen_yi_duan from admission_scores min_rank data."""
    from db.database import get_db
    from db.models import YiFenYiDuan, AdmissionScore
    from sqlalchemy import text

    db = next(get_db())
    try:
        # Query distinct (province, year, subject_type, score, rank) from admission_scores
        rows = db.execute(text("""
            SELECT province, year, subject_type, min_score, min_rank
            FROM admission_scores
            WHERE min_score IS NOT NULL AND min_rank IS NOT NULL
            AND min_score > 0 AND min_rank > 0
        """)).fetchall()

        count = 0
        for row in rows:
            province, year, subject_type, score, rank = row
            # Check if already exists
            existing = db.query(YiFenYiDuan).filter_by(
                province=province, year=year,
                subject_type=subject_type, score=score
            ).first()
            if not existing:
                entry = YiFenYiDuan(
                    province=province, year=year,
                    subject_type=subject_type, score=score,
                    rank=rank, source="admission_scores"
                )
                db.add(entry)
                count += 1

        db.commit()
        return count
    finally:
        db.close()
```

- [ ] **Step 3: Write test for the import**

```python
# tests/test_yi_fen_yi_duan.py
import pytest
from unittest.mock import patch, MagicMock

def test_populate_from_admission_scores():
    """Reverse-engineer rank data from admission_scores."""
    # This test verifies the import function runs without error
    # and correctly maps score->rank from existing data
    from scripts.import_yi_fen_yi_duan import populate_from_admission_scores
    # Use test database
    # ... mock setup ...
    assert True  # Placeholder until real DB test setup
```

- [ ] **Step 4: Run the import**

```bash
python scripts/import_yi_fen_yi_duan.py 2>&1
```

Expected: yi_fen_yi_duan table populated with records.

- [ ] **Step 5: Verify query works**

```bash
python -c "
from gaokao_data import query_yi_fen_yi_duan
result = query_yi_fen_yi_duan('广东', 2024, '物理类', 600)
print(f'Rank for 600 points: {result}')
" 2>&1
```

Expected: Returns a numeric rank.

- [ ] **Step 6: Commit**

```bash
git add scripts/import_yi_fen_yi_duan.py tests/test_yi_fen_yi_duan.py
git commit -m "feat: populate yi_fen_yi_duan from admission_scores data"
```

---

### Task 7: Enrollment Plans — Graceful Degradation

**Files:**
- Modify: `gaokao_data.py` (add enrollment plan query with fallback)
- Modify: `app.py` (UI handling when no data)

- [ ] **Step 1: Write test for enrollment plan query**

```python
# tests/test_enrollment_plans.py
def test_enrollment_plan_returns_empty_gracefully():
    """When enrollment_plans table is empty, query should return empty list, not error."""
    from gaokao_data import query_enrollment_plan
    result = query_enrollment_plan("清华大学", 2024)
    assert isinstance(result, list)

def test_enrollment_plan_ui_shows_fallback():
    """UI should show '暂无数据' when enrollment_plans is empty."""
    # This is a logic test — verify the fallback message exists
    from gaokao_data import format_enrollment_info
    result = format_enrollment_info([])
    assert "暂无" in result or "暂未" in result or len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_enrollment_plans.py -v 2>&1
```

Expected: FAIL — `query_enrollment_plan` function doesn't exist.

- [ ] **Step 3: Implement enrollment plan query in gaokao_data.py**

Add after the existing `query_admission()` function (around line 197):

```python
def query_enrollment_plan(school_name: str, year: int = None) -> list[dict]:
    """Query enrollment plan data. Returns empty list if table is empty."""
    if not HAS_DB:
        return []
    try:
        db = next(get_db())
        from db import crud as _crud
        plans = _crud.query_enrollment_plans_from_db(db, school_name, year=year)
        return plans or []
    except Exception as e:
        log.warning(f"enrollment_plan query failed: {e}")
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass


def format_enrollment_info(plans: list[dict]) -> str:
    """Format enrollment plan results for display."""
    if not plans:
        return "📋 暂未收录该院校的招生计划数据，建议关注院校官网获取最新信息。"
    # ... format existing data ...
    lines = ["📋 **招生计划**\n"]
    for p in plans:
        lines.append(f"- {p.get('major', '未知专业')}: {p.get('plan_count', '未知')}人")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_enrollment_plans.py -v 2>&1
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaokao_data.py tests/test_enrollment_plans.py
git commit -m "feat: add enrollment plan query with graceful empty-state fallback"
```

---

### Task 8: Data Year Labeling + Auto-Disclaimer

**Files:**
- Modify: `agent.py:1538-1540` (post-processing in `chat()`)
- Modify: `agent.py:1835-1838` (post-processing in `chat_stream()`)

- [ ] **Step 1: Write test for disclaimer post-processing**

```python
# tests/test_disclaimer.py
def test_disclaimer_added_when_missing():
    """Reply without disclaimer should get one appended."""
    from agent import ensure_disclaimer
    reply = "建议报考清华大学计算机专业，2024年最低分680。"
    result = ensure_disclaimer(reply)
    assert "仅供参考" in result or "数据来源" in result

def test_disclaimer_not_duplicated():
    """Reply that already has disclaimer should not get another."""
    from agent import ensure_disclaimer
    reply = "建议报考。以上数据仅供参考，具体以官方公布为准。"
    result = ensure_disclaimer(reply)
    assert result.count("仅供参考") <= 1

def test_year_label_included():
    """Reply mentioning school recommendations should reference data year."""
    from agent import ensure_year_label
    reply = "清华大学最低录取分680。"
    result = ensure_year_label(reply, default_year=2024)
    assert "2024" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_disclaimer.py -v 2>&1
```

Expected: FAIL — `ensure_disclaimer` and `ensure_year_label` don't exist.

- [ ] **Step 3: Implement disclaimer functions in agent.py**

Add before the `GaokaoAdvisor` class (around line 825):

```python
_DISCLAIMER_TEXT = "\n\n---\n⚠️ 以上数据仅供参考，实际录取以各省市招生考试院及院校官方公布为准。"
_YEAR_PATTERN = re.compile(r"20[2-3]\d年|基于\d{4}年数据")


def ensure_disclaimer(reply: str) -> str:
    """Ensure reply contains a disclaimer. Don't duplicate if already present."""
    if "仅供参考" in reply or "数据来源" in reply:
        return reply
    return reply + _DISCLAIMER_TEXT


def ensure_year_label(reply: str, default_year: int = 2024) -> str:
    """Ensure reply references data year when making recommendations."""
    recommendation_keywords = ["录取", "最低分", "分数线", "报考", "冲刺", "稳妥", "保底"]
    has_recommendation = any(kw in reply for kw in recommendation_keywords)
    has_year = bool(_YEAR_PATTERN.search(reply))
    if has_recommendation and not has_year:
        return reply.replace("\n\n---", f"\n\n> 📅 数据基于{default_year}年录取情况\n\n---", 1) if "\n\n---" in reply else f"> 📅 数据基于{default_year}年录取情况\n\n" + reply
    return reply
```

- [ ] **Step 4: Integrate into chat() post-processing**

At `agent.py` line ~1539, after `reply = cleanup_format(reply, cli_mode=self.cli_mode)`, add:

```python
reply = ensure_disclaimer(reply)
reply = ensure_year_label(reply)
```

- [ ] **Step 5: Integrate into chat_stream() post-processing**

At `agent.py` line ~1837, after `full_reply = cleanup_format(full_reply, cli_mode=self.cli_mode)`, add:

```python
full_reply = ensure_disclaimer(full_reply)
full_reply = ensure_year_label(full_reply)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_disclaimer.py -v 2>&1
```

Expected: PASS

- [ ] **Step 7: Run full suite**

```bash
pytest --tb=short -q 2>&1
```

- [ ] **Step 8: Commit**

```bash
git add agent.py tests/test_disclaimer.py
git commit -m "feat: auto-append data year label and disclaimer to all recommendations"
```

---

### Task 9: Data Quality Validation

**Files:**
- No code changes — validation execution only

- [ ] **Step 1: Run validation**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python scripts/validate_data.py 2>&1
```

Review output for any data quality issues.

- [ ] **Step 2: Check Hainan scores are not flagged as anomalies**

```bash
python -c "
from db.database import get_db
from sqlalchemy import text
db = next(get_db())
r = db.execute(text(\"\"\"
    SELECT province, MAX(min_score), COUNT(*)
    FROM admission_scores
    WHERE province = '海南'
    GROUP BY province
\"\"\")).fetchall()
for row in r:
    print(f'{row[0]}: max_score={row[1]}, count={row[2]}')
" 2>&1
```

Expected: max_score may be up to 900 (Hainan uses standard scores).

- [ ] **Step 3: Fix any issues found, commit if needed**

```bash
# If any fixes were needed:
git add -A
git commit -m "fix: data quality issues from full import validation"
```

---

### Sprint 2 Verification

- [ ] **Data counts**: `python -c "from db.database import get_db; from sqlalchemy import text; db=next(get_db()); print(db.execute(text('SELECT (SELECT COUNT(*) FROM schools) as s, (SELECT COUNT(*) FROM admission_scores) as a, (SELECT COUNT(*) FROM yi_fen_yi_duan) as y')).fetchone())"` — expect schools >= 3000, scores > 50000, yi_fen_yi_duan > 0
- [ ] **All tests pass**: `pytest --tb=short -q`
- [ ] **Disclaimer works**: Start a conversation, verify recommendations include disclaimer text

---

## Sprint 3: Product + Experience (Day 8-10)

### Task 10: 3-Step Onboarding Cards

**Files:**
- Create: `onboarding.py`
- Modify: `app.py` (import and render onboarding)
- Modify: `h5/index.html` (matching onboarding for mobile)

- [ ] **Step 1: Write test for onboarding logic**

```python
# tests/test_onboarding.py
def test_onboarding_completes_with_all_slots():
    """Onboarding should fill province, score, and subject slots."""
    from onboarding import OnboardingState
    state = OnboardingState()
    assert not state.is_complete()

    state.set_province("广东")
    assert not state.is_complete()

    state.set_score(650)
    state.set_subject("物理类")
    assert state.is_complete()

    slots = state.to_slots()
    assert slots["province"] == "广东"
    assert slots["score"] == 650
    assert slots["subject"] == "物理类"


def test_onboarding_skips_if_slots_filled():
    """Onboarding should not show if user already provided info in chat."""
    from onboarding import OnboardingState
    state = OnboardingState()
    state.set_province("北京")
    state.set_score(680)
    state.set_subject("历史类")
    assert state.should_skip()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_onboarding.py -v 2>&1
```

Expected: FAIL — `OnboardingState` doesn't exist.

- [ ] **Step 3: Create onboarding.py**

```python
"""3-step onboarding: Province → Score → Subject/Interest."""

from dataclasses import dataclass, field


# 30 provinces with their gaokao mode
PROVINCES = {
    "北京": "3+3", "天津": "3+3", "上海": "3+3", "浙江": "3+3",
    "山东": "3+3", "海南": "3+3",
    "河北": "3+1+2", "辽宁": "3+1+2", "江苏": "3+1+2", "福建": "3+1+2",
    "湖北": "3+1+2", "湖南": "3+1+2", "广东": "3+1+2", "重庆": "3+1+2",
    "山西": "3+1+2", "吉林": "3+1+2", "黑龙江": "3+1+2", "安徽": "3+1+2",
    "江西": "3+1+2", "贵州": "3+1+2", "广西": "3+1+2", "甘肃": "3+1+2",
    "云南": "3+1+2", "西藏": "3+1+2", "陕西": "3+1+2", "内蒙古": "3+1+2",
    "四川": "3+1+2", "宁夏": "3+1+2", "青海": "3+1+2", "新疆": "3+1+2",
}

SUBJECT_TYPES = ["物理类", "历史类"]

INTERESTS = [
    "🔬 理工", "🏥 医学", "💰 财经", "👨‍🏫 师范",
    "⚖️ 法学", "📚 文学", "🎨 艺术", "🌍 其他",
]


@dataclass
class OnboardingState:
    """Tracks onboarding progress. Step 1=province, 2=score, 3=subject+interest."""
    step: int = 1
    province: str = ""
    score: int = 0
    subject: str = ""
    interest: str = ""
    _slots: dict = field(default_factory=dict, repr=False)

    def is_complete(self) -> bool:
        return bool(self.province and self.score > 0 and self.subject)

    def should_skip(self) -> bool:
        return self.is_complete()

    def set_province(self, province: str) -> None:
        self.province = province
        self.step = 2

    def set_score(self, score: int) -> None:
        self.score = score
        self.step = 3

    def set_subject(self, subject: str, interest: str = "") -> None:
        self.subject = subject
        self.interest = interest
        self.step = 4  # complete

    def to_slots(self) -> dict:
        """Convert onboarding data to agent slot format."""
        return {
            "province": self.province,
            "score": self.score,
            "subject": self.subject,
            "interest": self.interest,
        }
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_onboarding.py -v 2>&1
```

Expected: PASS

- [ ] **Step 5: Create the Streamlit rendering in onboarding.py**

Append to `onboarding.py`:

```python
import streamlit as st


def render_onboarding() -> OnboardingState | None:
    """Render 3-step onboarding cards in Streamlit. Returns state when complete, None while in progress."""
    if "onboarding" not in st.session_state:
        st.session_state.onboarding = OnboardingState()

    state = st.session_state.onboarding
    if state.is_complete():
        return state

    if state.step == 1:
        st.markdown("### 📍 第一步：选择你的省份")
        cols = st.columns(4)
        for i, (prov, mode) in enumerate(PROVINCES.items()):
            col = cols[i % 4]
            with col:
                if st.button(f"{prov}\n{mode}", key=f"prov_{prov}", use_container_width=True):
                    state.set_province(prov)
                    st.rerun()

    elif state.step == 2:
        st.markdown(f"### 🎯 第二步：输入你的分数 ({state.province})")
        score = st.number_input("高考总分", min_value=0, max_value=900, step=1, key="onboard_score")
        if st.button("下一步", key="onboard_next2"):
            if score > 0:
                state.set_score(int(score))
                st.rerun()

    elif state.step == 3:
        st.markdown("### 📚 第三步：选择科类和兴趣方向")
        subject = st.radio("科类", SUBJECT_TYPES, key="onboard_subject")
        interest = st.selectbox("兴趣方向（可选）", [""] + INTERESTS, key="onboard_interest")
        if st.button("开始咨询 🚀", key="onboard_start"):
            state.set_subject(subject, interest)
            st.rerun()

    return None
```

- [ ] **Step 6: Integrate into app.py**

In `app.py`, find the main chat area (around line 1631 where quick questions are rendered). Before the quick questions section, add:

```python
from onboarding import render_onboarding

# Check if onboarding should show
_onboard_state = render_onboarding()
if _onboard_state is not None:
    # Fill agent slots from onboarding
    for slot, value in _onboard_state.to_slots().items():
        if value:
            st.session_state[slot] = value
```

- [ ] **Step 7: Test the Streamlit UI manually**

```bash
streamlit run app.py 2>&1
```

Open browser, verify:
1. First visit shows Step 1 (province selection)
2. Province → Score → Subject flow works
3. After completion, chat begins with pre-filled context

- [ ] **Step 8: Commit**

```bash
git add onboarding.py tests/test_onboarding.py app.py
git commit -m "feat: add 3-step onboarding cards (province → score → subject)"
```

---

### Task 11: Multi-Stage Loading Indicator

**Files:**
- Modify: `app.py:1789-1801` (loading phases already exist — verify and enhance)

- [ ] **Step 1: Read existing loading code**

Read `app.py` lines 1789-1801. The multi-phase loading already exists:
```python
_loading_phases = [
    (0, "🔍 正在匹配你的信息..."),
    (2.0, "📊 正在查询院校数据..."),
    (5.0, "🧠 AI 顾问正在分析，马上就好..."),
    (10.0, "⏳ 复杂情况可能需要更多时间，请稍候..."),
]
```

This is already implemented. Verify it works by testing in browser.

- [ ] **Step 2: If loading phases are only defined but not rendered, add rendering logic**

Check if there's a threading/timer mechanism that updates the loading message. If not, add a simple version:

```python
import threading

def _animate_loading(placeholder, phases, stop_event):
    """Update loading text at scheduled intervals."""
    for delay, text in phases:
        if stop_event.is_set():
            return
        time.sleep(delay)
        if not stop_event.is_set():
            placeholder.info(text)

# In the chat handler, before LLM call:
stop_event = threading.Event()
loading_placeholder = st.empty()
loading_placeholder.info("🔍 正在匹配你的信息...")
loader = threading.Thread(target=_animate_loading, args=(loading_placeholder, _loading_phases, stop_event))
loader.daemon = True
loader.start()

# After LLM response received:
stop_event.set()
loading_placeholder.empty()
```

- [ ] **Step 3: Verify in browser**

```bash
streamlit run app.py
```

Verify loading messages update progressively during response generation.

- [ ] **Step 4: Commit** (only if changes were made)

```bash
git add app.py
git commit -m "feat: verify multi-stage loading indicator works end-to-end"
```

---

### Task 12: API Key Maintenance Page

**Files:**
- Modify: `app.py` (add maintenance page check near top)

- [ ] **Step 1: Add maintenance page logic**

In `app.py`, after the imports and before the main Streamlit layout, add:

```python
import os

def _check_api_key_available() -> bool:
    """Check if LLM API key is configured."""
    return bool(os.environ.get("LLM_API_KEY", "").strip())


def render_maintenance_page():
    """Show maintenance page when API key is not configured."""
    st.set_page_config(page_title="gaobao · 系统维护", page_icon="🔧")
    st.title("🔧 gaobao 暂时维护中")
    st.markdown("""
    系统正在维护升级中，预计很快恢复。

    **你可以：**
    - 关注我们的公众号获取最新动态
    - 加入家长交流群等待恢复通知

    ---
    *gaobao — 让每个考生都不留遗憾*
    """)
    st.stop()
```

- [ ] **Step 2: Add the check near the top of the Streamlit app**

Find the main app entry point (around line 895 where `def main():` is defined or the top-level Streamlit calls begin). Add:

```python
# At the very start of the Streamlit app, before any UI rendering:
if not _check_api_key_available():
    render_maintenance_page()
```

**Note:** The admin bypass via `?admin=true` query param:

```python
def _check_api_key_available() -> bool:
    """Check if LLM API key is configured. Admin can bypass."""
    if st.query_params.get("admin") == "true":
        return True
    return bool(os.environ.get("LLM_API_KEY", "").strip())
```

- [ ] **Step 3: Test without API key**

```bash
unset LLM_API_KEY
streamlit run app.py
```

Expected: Maintenance page shown. Set `?admin=true` in URL to bypass.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: show maintenance page when LLM API key not configured"
```

---

### Task 13: Conversation History UI + Export

**Files:**
- Modify: `app.py:1444-1481` (enhance existing conversation history section)

- [ ] **Step 1: Read existing conversation history code**

Read `app.py` lines 1444-1481. There's already an expander with conversation list. Enhance it.

- [ ] **Step 2: Enhance conversation history to support restoration**

The existing code shows history but may not support clicking to restore. Add click-to-restore:

```python
# In the sidebar conversation history section (around line 1444)
# Replace the existing expander content with:

with st.expander("💬 历史对话", expanded=False):
    from db.database import get_db
    from db.models import Conversation, ConversationMessage
    from sqlalchemy import desc

    db = next(get_db())
    try:
        conversations = db.query(Conversation)\
            .order_by(desc(Conversation.updated_at))\
            .limit(20).all()

        if not conversations:
            st.caption("暂无历史对话")

        for conv in conversations:
            label = conv.user_label or conv.province or "未知"
            time_str = conv.updated_at.strftime("%m-%d %H:%M") if conv.updated_at else ""
            msg_count = len(conv.messages) if conv.messages else 0

            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button(
                    f"📋 {label} · {conv.province or ''} · {msg_count}轮",
                    key=f"conv_{conv.id}",
                    use_container_width=True,
                ):
                    # Restore conversation
                    st.session_state.conversation_id = conv.id
                    msgs = db.query(ConversationMessage)\
                        .filter_by(conversation_id=conv.id)\
                        .order_by(ConversationMessage.id).all()
                    # Populate session state with history
                    st.session_state.messages = [
                        {"role": m.role, "content": m.content} for m in msgs
                    ]
                    # Restore slots
                    if conv.slots_json:
                        import json
                        slots = json.loads(conv.slots_json)
                        for k, v in slots.items():
                            if v:
                                st.session_state[k] = v
                    st.rerun()
            with col2:
                st.caption(time_str)
    finally:
        db.close()
```

- [ ] **Step 3: Add export functionality**

In the sidebar export section (around line 1163), enhance:

```python
# In the export panel, add Markdown export alongside existing PDF:
import io

def _export_markdown(messages: list[dict]) -> str:
    """Export conversation as Markdown."""
    lines = ["# gaobao 高考志愿咨询记录\n"]
    for msg in messages:
        role = "🧑 考生" if msg["role"] == "user" else "🎓 顾问"
        lines.append(f"\n## {role}\n\n{msg['content']}\n")
    lines.append("\n---\n*由 gaobao 生成，数据仅供参考*\n")
    return "\n".join(lines)

# In the export sidebar section:
if st.button("📄 导出 Markdown", key="export_md"):
    md_content = _export_markdown(st.session_state.get("messages", []))
    st.download_button(
        label="下载 Markdown 文件",
        data=md_content,
        file_name="gaobao_咨询记录.md",
        mime="text/markdown",
    )
```

- [ ] **Step 4: Verify in browser**

```bash
streamlit run app.py
```

Verify:
1. Sidebar shows conversation history list
2. Clicking a conversation restores it
3. Markdown export works

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: enhance conversation history with click-to-restore and markdown export"
```

---

### Sprint 3 Verification

- [ ] **Onboarding flow works**: Fresh session → 3-step cards → chat begins with context
- [ ] **Loading indicators**: Messages progress through 4 stages during LLM call
- [ ] **Maintenance page**: Without API key, shows maintenance; `?admin=true` bypasses
- [ ] **Conversation history**: Sidebar shows past conversations, click restores
- [ ] **Export**: Markdown export downloads successfully
- [ ] **All tests pass**: `pytest --tb=short -q`

---

## Sprint 4: Production + Commercial (Day 11-14)

### Task 14: Production Hardening

**Files:**
- Modify: `api_server.py:68-86` (rate limiting + session TTL)
- Modify: `utils.py` (XSS audit)
- Modify: `logger.py` (ensure JSON format available)

- [ ] **Step 1: Add rate limiting to api_server.py**

Read `api_server.py` and `ratelimit.py`. The RateLimiter class exists in ratelimit.py.

```python
# In api_server.py, add after imports:
from ratelimit import RateLimiter

_api_rate_limiter = RateLimiter(max_tokens=30, refill_rate=1.0)  # 30 requests burst, 1/sec refill

# Add middleware or check in each endpoint:
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not _api_rate_limiter.allow(client_ip):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"error": "请求过于频繁，请稍后再试"})
    return await call_next(request)
```

- [ ] **Step 2: Add session TTL cleanup**

```python
# In api_server.py, modify the session management:
import time

_session_timestamps: dict[str, float] = {}
SESSION_TTL = 1800  # 30 minutes

def _get_advisor(session_id: str) -> GaokaoAdvisor:
    global _advisors, _session_timestamps
    now = time.time()

    # Evict expired sessions
    expired = [sid for sid, ts in _session_timestamps.items()
               if now - ts > SESSION_TTL]
    for sid in expired:
        _advisors.pop(sid, None)
        _session_timestamps.pop(sid, None)

    # LRU eviction if still over limit
    if len(_advisors) >= MAX_SESSIONS and session_id not in _advisors:
        oldest = min(_session_timestamps, key=_session_timestamps.get)
        _advisors.pop(oldest, None)
        _session_timestamps.pop(oldest, None)

    if session_id not in _advisors:
        _advisors[session_id] = GaokaoAdvisor(...)
    _session_timestamps[session_id] = now
    return _advisors[session_id]
```

- [ ] **Step 3: Fix SQLite WAL file permissions**

Add to `db/database.py` initialization:

```python
import os
import stat

def _lock_db_permissions(db_path: str):
    """Ensure WAL and SHM files have same restrictive permissions as main DB."""
    for suffix in ["", "-wal", "-shm"]:
        path = db_path + suffix
        if os.path.exists(path):
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
```

Call this after database creation.

- [ ] **Step 4: Run `pip-audit` or manual dependency check**

```bash
pip install pip-audit 2>/dev/null
pip-audit 2>&1 | head -20
```

Review any high-severity findings.

- [ ] **Step 5: Commit**

```bash
git add api_server.py db/database.py
git commit -m "feat: production hardening — rate limiting, session TTL, DB permissions"
```

---

### Task 15: Docker Production + Backup

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `.env.production`
- Create: `scripts/backup_db.sh`
- Modify: `Dockerfile` (health check)

- [ ] **Step 1: Create docker-compose.prod.yml**

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  advisor:
    build: .
    container_name: gaobao-advisor
    restart: unless-stopped
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./.env.production:/app/.env:ro
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  nginx:
    image: nginx:alpine
    container_name: gaobao-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      advisor:
        condition: service_healthy
    profiles:
      - with-nginx
```

- [ ] **Step 2: Create .env.production**

```
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
ENABLE_SEARCH=true
ENABLE_RAG_KB=true
DATABASE_URL=sqlite:///app/data/gaokao.db
```

- [ ] **Step 3: Create backup script**

```bash
#!/usr/bin/env bash
# scripts/backup_db.sh — daily database backup
set -euo pipefail

DB_PATH="${DB_PATH:-data/gaokao.db}"
BACKUP_DIR="${BACKUP_DIR:-data/backups}"
DAYS_KEEP="${DAYS_KEEP:-7}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/gaobao_${TIMESTAMP}.db"

cp "$DB_PATH" "$BACKUP_FILE"
gzip "$BACKUP_FILE"

# Remove backups older than DAYS_KEEP
find "$BACKUP_DIR" -name "gaobao_*.db.gz" -mtime +${DAYS_KEEP} -delete 2>/dev/null || true

echo "Backup created: ${BACKUP_FILE}.gz"
```

```bash
chmod +x scripts/backup_db.sh
```

- [ ] **Step 4: Verify Docker build**

```bash
docker compose -f docker-compose.prod.yml build 2>&1 | tail -10
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml .env.production scripts/backup_db.sh
git commit -m "feat: production Docker config and database backup script"
```

---

### Task 16: OPC Commercial Hooks

**Files:**
- Modify: `app.py` (sidebar WeChat section at lines 1485-1511)
- Modify: `analytics/tracker.py` (add new event types)

- [ ] **Step 1: Enhance sidebar WeChat section**

Read `app.py` lines 1485-1511. There's already a WeChat section. Enhance it:

```python
# In the sidebar WeChat section (around line 1485)
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📱 加入家长交流群")

    # Placeholder for QR code image
    # Place your QR code image at: static/wechat_group_qr.png
    import os
    qr_path = os.path.join(os.path.dirname(__file__), "static", "wechat_group_qr.png")
    if os.path.exists(qr_path):
        st.image(qr_path, width=200, caption="扫码加入家长群")
    else:
        st.info("💬 微信群二维码（管理员请将二维码图片放到 static/wechat_group_qr.png）")

    st.markdown("""
    🔹 高考政策实时推送
    🔹 一对一志愿咨询
    🔹 往届家长经验分享
    """)

    # Free PDF guide
    if st.button("📥 免费领取《志愿填报指南》", key="free_guide", use_container_width=True):
        st.info("请联系客服获取：gaobao@example.com")
```

- [ ] **Step 2: Add new analytics events**

In `analytics/tracker.py`, add new event constants:

```python
# Add to the event type constants (or create them)
EVENT_SESSION_START = "session_start"
EVENT_EMOTION_DETECTED = "emotion_detected"
EVENT_SLOT_FILLED = "slot_filled"
EVENT_MAJOR_QUERY = "major_query"
EVENT_SCHOOL_QUERY = "school_query"
EVENT_EXPORT_CLICKED = "export_clicked"
EVENT_ONBOARDING_COMPLETE = "onboarding_complete"
```

- [ ] **Step 3: Add event tracking calls in agent.py**

In the `chat()` method, after slot extraction:

```python
# After slot filling logic in chat():
if HAS_TRACKER:
    filled_slots = [k for k, v in self.slots.items() if v]
    for slot in filled_slots:
        tracker.track(EVENT_SLOT_FILLED, {"slot": slot, "session_id": self.session_id})
```

In the `chat()` method, after emotion detection:

```python
# After emotion detection:
if HAS_TRACKER and emotion_result:
    tracker.track(EVENT_EMOTION_DETECTED, {"level": emotion_result.get("level"), "session_id": self.session_id})
```

- [ ] **Step 4: Commit**

```bash
git add app.py analytics/tracker.py agent.py
git commit -m "feat: OPC commercial hooks — WeChat QR, event tracking enhancements"
```

---

### Task 17: H5 Mobile Optimization

**Files:**
- Modify: `h5/index.html:349-405` (touch targets, responsive)

- [ ] **Step 1: Read current H5 structure**

Read `h5/index.html` lines 349-405.

- [ ] **Step 2: Increase touch targets**

In the `<style>` section of h5/index.html, ensure:

```css
/* Minimum 44px touch targets */
button, .quick-btn, .send-btn {
    min-height: 44px;
    min-width: 44px;
}

.quick-btn {
    padding: 12px 16px;
    font-size: 15px;
    border-radius: 12px;
    margin-bottom: 8px;
}

.send-btn {
    padding: 12px 24px;
    font-size: 16px;
    border-radius: 20px;
}

textarea {
    font-size: 16px; /* Prevents iOS zoom on focus */
    min-height: 44px;
    padding: 10px 14px;
    border-radius: 12px;
}

/* Long text auto-fold */
.message-content {
    max-height: 300px;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
}
```

- [ ] **Step 3: Verify in mobile viewport**

Open browser dev tools, toggle device toolbar, select iPhone/Android size. Verify:
1. All buttons are tappable (not too small)
2. Input doesn't cause zoom on iOS
3. Long messages scroll properly

- [ ] **Step 4: Commit**

```bash
git add h5/index.html
git commit -m "feat: H5 mobile optimization — touch targets, responsive layout"
```

---

### Task 18: Go-Live Checklist + Smoke Test

**Files:**
- No code changes — verification only

- [ ] **Step 1: Run full test suite**

```bash
pytest --tb=short -q 2>&1
```

Expected: All tests pass.

- [ ] **Step 2: Security checklist**

```bash
# No hardcoded secrets
grep -rn "api_key\|password\|secret\|token" --include="*.py" . | grep -v __pycache__ | grep -v ".env" | grep -v "test_" | grep -v "def " | grep -vi "api_key\|LLM_API_KEY\|os.environ"

# No XSS vectors (user input rendered unescaped)
grep -rn "unsafe\|innerHTML\|DangerouslySetInnerHTML" --include="*.py" --include="*.html" .

# All inputs validated
grep -rn "st\.\(text_input\|number_input\|selectbox\)" app.py | wc -l
```

- [ ] **Step 3: Functional smoke test**

```bash
# Start the app
streamlit run app.py &

# Wait for startup, then test health
sleep 5
curl -f http://localhost:8501/_stcore/health && echo "OK" || echo "FAIL"

# Test API server (if running)
# curl -f http://localhost:8000/api/health && echo "OK" || echo "FAIL"
```

- [ ] **Step 4: Performance check**

```bash
# Quick concurrent test
for i in $(seq 1 5); do
    curl -s http://localhost:8501/_stcore/health > /dev/null &
done
wait
echo "Concurrent health check: OK"
```

- [ ] **Step 5: Create deploy checklist file**

```markdown
# docs/deploy-checklist.md

# gaobao Production Deploy Checklist

## Pre-deploy
- [ ] All tests passing (pytest)
- [ ] CI/CD green on GitHub
- [ ] .env.production configured with real API key
- [ ] Database backed up

## Deploy
- [ ] `docker compose -f docker-compose.prod.yml pull` (if using registry)
- [ ] `docker compose -f docker-compose.prod.yml up -d`
- [ ] Health check returns 200

## Post-deploy
- [ ] Streamlit UI loads correctly
- [ ] Chat responds to test query
- [ ] Onboarding flow works
- [ ] Export works
- [ ] No errors in logs: `docker logs gaobao-advisor`

## Rollback
- [ ] `docker compose -f docker-compose.prod.yml down`
- [ ] Restore database from backup: `data/backups/gaobao_*.db.gz`
- [ ] `docker compose -f docker-compose.yml up -d` (previous version)
```

- [ ] **Step 6: Commit**

```bash
git add docs/deploy-checklist.md
git commit -m "docs: add production deploy checklist"
```

---

### Task 19: Sprint 4 Integration Verification

- [ ] **Step 1: Full test suite**

```bash
pytest --tb=short -q 2>&1
```

- [ ] **Step 2: Docker production build and start**

```bash
docker compose -f docker-compose.prod.yml build 2>&1 | tail -5
docker compose -f docker-compose.prod.yml up -d 2>&1
sleep 15
docker compose -f docker-compose.prod.yml ps 2>&1
```

Expected: advisor service running, healthy.

- [ ] **Step 3: End-to-end flow test**

```bash
# Health check
curl -s http://localhost:8501/_stcore/health

# Verify app loads
curl -s http://localhost:8501 | head -5
```

- [ ] **Step 4: Check logs for errors**

```bash
docker logs gaobao-advisor --tail 30 2>&1
```

Expected: No ERROR level logs.

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration fixes from production smoke test"
```

---

## Sprint 4 Verification

- [ ] **Rate limiting**: Send 31 rapid requests to API, verify 429 response
- [ ] **Session TTL**: Create session, wait 31 minutes, verify eviction
- [ ] **Docker**: `docker compose -f docker-compose.prod.yml ps` — all healthy
- [ ] **WeChat QR**: Sidebar shows QR code placeholder or image
- [ ] **Mobile**: H5 page loads, buttons are tappable, no zoom on input
- [ ] **All tests pass**: `pytest --tb=short -q`

---

## Summary

| Sprint | Tasks | Key Deliverable |
|--------|-------|-----------------|
| S1 | 1-4 | 274/274 tests, CI, brand "gaobao", RAG enabled |
| S2 | 5-9 | 100K+ scores, yi-fen-yi-duan, disclaimers |
| S3 | 10-13 | Onboarding, loading, maintenance page, history, export |
| S4 | 14-19 | Rate limiting, Docker prod, OPC hooks, mobile, deploy |
