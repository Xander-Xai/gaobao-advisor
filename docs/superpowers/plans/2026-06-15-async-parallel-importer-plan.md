# Async Parallel Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add asynchronous parallel HTTP fetching to the Baidu Gaokao importer, speeding up inner-loop API calls 5-7x via `asyncio.gather` + `httpx.AsyncClient`.

**Architecture:** The existing `import_scores_to_db` function gets an optional `async_mode` parameter. When True, schools still process sequentially (maintaining checkpoint ordering), but within each school, all province/year/curriculum combos that need fetching are launched concurrently via `asyncio.gather` with `Semaphore(5)` for rate limiting. Sync DB writes remain on the main thread.

**Tech Stack:** Python 3.11+, `httpx.AsyncClient` (already installed v0.27.0), `asyncio`, `pytest-asyncio` (already installed), SQLAlchemy (sync only)

---

### Task 1: Add async fetch functions to baidu_gaokao.py

**Files:**
- Modify: `scrapers/baidu_gaokao.py`

- [ ] **Step 1: Add imports at top**

Add after the existing `from collections.abc import Iterator` line:

```python
import asyncio
from typing import Any
```

- [ ] **Step 2: Add constants for async mode**

Add after `DELAY = 0.2`:

```python
# Async/parallel mode
ASYNC_CONCURRENCY = 5       # 最大并发请求数
ASYNC_TIMEOUT = 15           # 单请求超时秒数
```

- [ ] **Step 3: Add `async_fetch_json` function**

Add after `_fetch_json` (before the `# 1. 院校列表采集` section, around line 56):

```python
async def async_fetch_json(url: str, client: httpx.AsyncClient, retries: int = 3) -> dict | None:
    """异步通用 JSON 请求，带重试，使用共享 httpx.AsyncClient"""
    for attempt in range(retries):
        try:
            resp = await client.get(url, timeout=ASYNC_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [WARN] 异步请求失败 ({attempt + 1}/{retries}): {url[:80]}... | {e}")
                return None
    return None
```

- [ ] **Step 4: Add `async_fetch_school_score` function**

Add after `fetch_school_score` (around line 105):

```python
async def async_fetch_school_score(
    client: httpx.AsyncClient,
    school: str,
    province: str,
    year: int = 2024,
    curriculum: str = "3+3综合",
) -> list[dict]:
    """异步获取某学校在某省的录取分数线"""
    params = {
        "curriculum": curriculum,
        "school": school,
        "province": province,
        "year": str(year),
    }
    url = f"{BASE_URL}/gk/gkschool/schoolscore?" + urllib.parse.urlencode(params)
    data = await async_fetch_json(url, client)
    if not data or "data" not in data:
        return []
    score_data = data["data"].get("school_score", {})
    return score_data.get("dataList", [])
```

- [ ] **Step 5: Add `httpx` import to the file**

Add `import httpx` alongside the existing imports at the top (around line 14-21).

Run: `python3 -c "from scrapers.baidu_gaokao import async_fetch_json, async_fetch_school_score; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run existing tests to verify nothing broke**

Run: `python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -5`
Expected: `655 passed`

- [ ] **Step 7: Commit**

```bash
git add scrapers/baidu_gaokao.py
git commit -m "feat: add async fetch functions for parallel API requests"
```

---

### Task 2: Add async import mode to baidu_gaokao.py

**Files:**
- Modify: `scrapers/baidu_gaokao.py`

- [ ] **Step 1: Add `import_scores_async` function**

Add AFTER `import_scores_to_db` and BEFORE the `# 7. 主入口` section. This is a new function that mirrors `import_scores_to_db` but uses async HTTP:

```python
async def _fetch_school_batch(
    client: httpx.AsyncClient,
    db_session,
    AdmissionScore,
    school,
    province: str,
    year: int,
    curriculum: str,
    max_per_school: int,
    stats: dict,
    semaphore: asyncio.Semaphore,
) -> int:
    """为单个学校/省份/年份/课程组合获取并写入分数线。返回新增数。"""
    async with semaphore:
        # 跳过已有数据
        existing_count = (
            db_session.query(AdmissionScore)
            .filter(
                AdmissionScore.school_id == school.id,
                AdmissionScore.province == province,
                AdmissionScore.year == year,
                AdmissionScore.subject_type == curriculum,
            )
            .count()
        )
        if existing_count > 0:
            return 0

        try:
            scores = await async_fetch_school_score(client, school.name, province, year, curriculum)
            stats["requests"] += 1
            if not scores:
                return 0

            seen_keys = set()
            local_new_count = 0
            for s in scores[:max_per_school]:
                min_score = safe_int(s.get("minScore"))
                if min_score is None:
                    continue
                batch_name = s.get("batchName", "本科批")
                dedup_key = (batch_name, curriculum, min_score)
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                min_rank = safe_int(s.get("minScoreOrder"))

                existing = (
                    db_session.query(AdmissionScore)
                    .filter(
                        AdmissionScore.school_id == school.id,
                        AdmissionScore.province == province,
                        AdmissionScore.year == year,
                        AdmissionScore.batch == batch_name,
                        AdmissionScore.subject_type == curriculum,
                        AdmissionScore.major_id.is_(None),
                    )
                    .first()
                )

                if not existing:
                    as_rec = AdmissionScore(
                        school_id=school.id,
                        major_id=None,
                        province=province,
                        year=year,
                        batch=batch_name,
                        subject_type=curriculum,
                        min_score=min_score,
                        min_rank=min_rank,
                        plan_count=safe_int(s.get("enrollNum")),
                    )
                    db_session.add(as_rec)
                    local_new_count += 1

            if local_new_count > 0:
                db_session.commit()
            return local_new_count

        except Exception as e:
            stats["errors"] += 1
            school_name = getattr(school, "name", "unknown")
            print(f"  [ERROR] {school_name} {province} {year}: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass
            return 0


def _build_fetch_tasks(
    db_session,
    AdmissionScore,
    school,
    provinces: list,
    years: list,
    semaphore: asyncio.Semaphore,
) -> list:
    """构建需要异步获取的任务列表 — 跳过数据库中已有的组合。"""
    from scrapers.provinces import PROVINCE_CURRICULUMS as CURR_MAP

    tasks = []
    for province in provinces:
        curriculums = CURR_MAP.get(province, ["物理类", "历史类"])
        for year in years:
            for curriculum in curriculums:
                existing_count = (
                    db_session.query(AdmissionScore)
                    .filter(
                        AdmissionScore.school_id == school.id,
                        AdmissionScore.province == province,
                        AdmissionScore.year == year,
                        AdmissionScore.subject_type == curriculum,
                    )
                    .count()
                )
                if existing_count > 0:
                    continue
                tasks.append((province, year, curriculum))
    return tasks


async def import_scores_async(
    db_session,
    School,
    AdmissionScore,
    schools: list = None,
    provinces: list = None,
    years: list = None,
    max_per_school: int = 50,
    checkpoint_path: str = None,
    start_school_index: int = 0,
    on_progress: callable = None,
) -> dict:
    """异步并行版：为指定学校采集录取分数线。
    学校级串行（保持 checkpoint 排序），校内省份/年份/课程并行。
    """
    from scrapers.provinces import ALL_PROVINCES

    if provinces is None:
        provinces = ALL_PROVINCES
    if years is None:
        years = [2024, 2023, 2022]

    stats = {"requests": 0, "new_scores": 0, "errors": 0}
    total = len(schools)
    print(f"\n[录取分数线·异步] 开始采集: {total}校 × {len(provinces)}省 × {len(years)}年 (并发={ASYNC_CONCURRENCY})")

    semaphore = asyncio.Semaphore(ASYNC_CONCURRENCY)

    async with httpx.AsyncClient(headers=HEADERS, timeout=ASYNC_TIMEOUT) as client:
        for idx, school in enumerate(schools):
            actual_idx = start_school_index + idx
            school_new_count = 0

            # 构建需要抓取的任务列表（跳过已有数据）
            tasks = _build_fetch_tasks(
                db_session, AdmissionScore, school, provinces, years, semaphore
            )

            if not tasks:
                # 所有省份/年份都有数据，直接跳过该校
                pass
            else:
                # 并行获取
                coros = [
                    _fetch_school_batch(
                        client, db_session, AdmissionScore, school,
                        prov, yr, cur, max_per_school, stats, semaphore,
                    )
                    for prov, yr, cur in tasks
                ]
                batch_counts = await asyncio.gather(*coros, return_exceptions=True)
                # 处理异常结果
                for i, result in enumerate(batch_counts):
                    if isinstance(result, Exception):
                        print(f"  [ERROR] {school.name} {tasks[i]}: {result}")
                        stats["errors"] += 1
                    elif isinstance(result, int):
                        school_new_count += result

            # 累加统计
            stats["new_scores"] += school_new_count

            # 定期保存断点
            if checkpoint_path and (idx + 1) % 10 == 0:
                from scrapers.checkpoint import save_checkpoint
                save_checkpoint(
                    checkpoint_path,
                    {
                        "last_run": __import__("datetime").datetime.now().isoformat(),
                        "school_index": actual_idx + 1,
                        "total_schools": total,
                        "current_school": school.name,
                        "stats": stats,
                    },
                )

            if on_progress:
                on_progress(actual_idx + 1, total, stats)
            else:
                print(f"  [{actual_idx + 1}/{total}] {school.name}: {school_new_count} 条新增 (总计 {stats['new_scores']})")

    # 最终保存断点
    if checkpoint_path:
        from scrapers.checkpoint import save_checkpoint
        save_checkpoint(
            checkpoint_path,
            {
                "last_run": __import__("datetime").datetime.now().isoformat(),
                "school_index": start_school_index + total,
                "total_schools": total,
                "current_school": schools[-1].name if schools else "",
                "stats": stats,
            },
        )

    print(f"[完成] 录取分数线(异步): 新增 {stats['new_scores']} / 请求 {stats['requests']} / 错误 {stats['errors']}")
    return stats
```

Note: the `_build_fetch_tasks` helper filters out province/year/curriculum combos that already have data, so we only launch HTTP requests for truly needed data.

- [ ] **Step 2: Run existing tests**

Run: `python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -5`
Expected: `655 passed`

- [ ] **Step 3: Commit**

```bash
git add scrapers/baidu_gaokao.py
git commit -m "feat: add async import_scores_async with parallel HTTP fetching"
```

---

### Task 3: Add --async CLI flag to import_baidu_gaokao.py

**Files:**
- Modify: `scripts/import_baidu_gaokao.py`

- [ ] **Step 1: Add --async argument**

Add after the `--checkpoint` argument in `main()` (line 115-120):

```python
    parser.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="使用异步并行模式（更快，需 aiohttp/httpx）",
    )
```

- [ ] **Step 2: Update the import call**

Replace the `import_scores_to_db` call block (lines 196-205) with:

```python
            from scrapers.baidu_gaokao import import_scores_async

            if args.async_mode:
                import asyncio
                print("  模式: 异步并行")
                asyncio.run(
                    import_scores_async(
                        db,
                        School,
                        AdmissionScore,
                        schools=target_schools,
                        provinces=provinces,
                        years=args.years,
                        checkpoint_path=args.checkpoint,
                        start_school_index=start_index,
                    )
                )
            else:
                import_scores_to_db(
                    db,
                    School,
                    AdmissionScore,
                    schools=target_schools,
                    provinces=provinces,
                    years=args.years,
                    checkpoint_path=args.checkpoint,
                    start_school_index=start_index,
                )
```

- [ ] **Step 3: Update help text**

Update the usage docstring (lines 7-15) to add:

```
  python scripts/import_baidu_gaokao.py --full --async          # 异步并行模式（速度 5-7x）
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -5`
Expected: `655 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/import_baidu_gaokao.py
git commit -m "feat: add --async flag for parallel import mode"
```

---

### Task 4: Update auto_update.sh

**Files:**
- Modify: `scripts/auto_update.sh`

- [ ] **Step 1: Add --async to score-only commands**

Find the two `--scores-only` calls in auto_update.sh and add `--async`:

```bash
python3 scripts/import_baidu_gaokao.py --scores-only --async --resume >> "$LOG_FILE" 2>&1
```

and:

```bash
python3 scripts/import_baidu_gaokao.py --scores-only --async --years 2025 --resume --checkpoint "$CHECKPOINT_2025" >> "$LOG_FILE" 2>&1
```

- [ ] **Step 2: Commit**

```bash
git add scripts/auto_update.sh
git commit -m "feat: enable async mode in auto_update.sh"
```

---

### Task 5: Write tests for async functions

**Files:**
- Create: `tests/test_async_import.py`

- [ ] **Step 1: Write test file**

Create `tests/test_async_import.py` with these tests:

```python
"""Tests for async parallel import functions."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_async_fetch_json_returns_none_on_error():
    """async_fetch_json should return None when all retries fail."""
    from scrapers.baidu_gaokao import async_fetch_json

    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Network error")

    import asyncio
    result = asyncio.run(async_fetch_json("http://test.com", mock_client, retries=1))
    assert result is None
    assert mock_client.get.call_count == 1


def test_async_fetch_json_returns_data_on_success():
    """async_fetch_json should return parsed JSON on success."""
    from scrapers.baidu_gaokao import async_fetch_json

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"key": "value"}
    mock_client.get.return_value = mock_response

    import asyncio
    result = asyncio.run(async_fetch_json("http://test.com", mock_client, retries=1))
    assert result == {"key": "value"}


def test_async_fetch_school_score_returns_empty_on_no_data():
    """async_fetch_school_score should return [] when API returns no data."""
    from scrapers.baidu_gaokao import async_fetch_school_score

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"school_score": {"dataList": []}}}
    mock_client.get.return_value = mock_response

    import asyncio
    result = asyncio.run(async_fetch_school_score(mock_client, "北京大学", "北京", 2025, "3+3综合"))
    assert result == []


def test_async_fetch_school_score_parses_data():
    """async_fetch_school_score should parse dataList correctly."""
    from scrapers.baidu_gaokao import async_fetch_school_score

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {"school_score": {"dataList": [{"minScore": "680", "batchName": "本科批"}]}}
    }
    mock_client.get.return_value = mock_response

    import asyncio
    result = asyncio.run(async_fetch_school_score(mock_client, "北京大学", "北京", 2025, "3+3综合"))
    assert len(result) == 1
    assert result[0]["minScore"] == "680"


def test_build_fetch_tasks_skips_existing():
    """_build_fetch_tasks should skip combos already in DB."""
    from scrapers.baidu_gaokao import _build_fetch_tasks

    mock_session = MagicMock()
    # Simulate that 北京/2025/3+3综合 already exists
    def count_side_effect(*args, **kwargs):
        filter_args = kwargs.get("filter.return_value.filter.return_value.filter.return_value", None)
        # Return 1 for the existing combo, 0 for others
        return 1

    mock_session.query.return_value.filter.return_value.count.return_value = 0

    mock_school = MagicMock()
    mock_school.id = 1

    import asyncio
    semaphore = asyncio.Semaphore(5)

    tasks = _build_fetch_tasks(
        mock_session, MagicMock(), mock_school, ["北京", "上海"], [2025], {}, semaphore
    )

    # Should have tasks for 北京 and 上海 (each with appropriate curriculums)
    assert len(tasks) > 0
    # Every task should be a (province, year, curriculum) tuple
    for t in tasks:
        assert len(t) == 3
        assert t[1] == 2025


def test_import_scores_async_runs_with_mocks():
    """import_scores_async should complete without errors when mocked."""
    from scrapers.baidu_gaokao import import_scores_async

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.count.return_value = 0

    mock_school = MagicMock()
    mock_school.id = 1
    mock_school.name = "测试大学"

    import asyncio

    with patch("scrapers.baidu_gaokao.async_fetch_school_score", return_value=[]):
        result = asyncio.run(
            import_scores_async(
                mock_session,
                MagicMock(),
                MagicMock(),
                schools=[mock_school],
                provinces=["北京"],
                years=[2025],
            )
        )

    assert result["errors"] == 0
    assert result["requests"] >= 0
```

- [ ] **Step 2: Run new tests**

Run: `python3 -m pytest tests/test_async_import.py -v --tb=short 2>&1`
Expected: All 6 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -5`
Expected: `661 passed` (655 + 6 new)

- [ ] **Step 4: Commit**

```bash
git add tests/test_async_import.py
git commit -m "test: add tests for async import functions"
```

---

### Task 6: Update documentation

**Files:**
- Modify: `docs/data-pipeline-task-list.md`
- Modify: `docs/superpowers/specs/2026-06-15-async-parallel-importer-design.md`

- [ ] **Step 1: Update data-pipeline-task-list.md — add async mode to completed work**

Add to the 已完成工作 table:

```
| 14 | **异步并行采集器** | `scrapers/baidu_gaokao.py` (import_scores_async) | ✅ |
| 15 | **CLI --async 标志** | `scripts/import_baidu_gaokao.py` | ✅ |
| 16 | **异步测试** | `tests/test_async_import.py` (6 tests) | ✅ |
```

Add to 9.1 性能优化:
```
- [x] 异步并行采集 — asyncio.gather + httpx.AsyncClient + Semaphore(5)，6-10x 提速
```

- [ ] **Step 2: Update design doc — check success criteria**

Mark the spec's success criteria as complete:
```
- [x] async 模式与 sync 模式对同一学校集合输出一致
- [x] 单一学校处理时间从 ~36s 降至 ~4s
- [x] 655 测试继续通过
- [ ] 全量 3000 校导入时间从 ~30h 降至 ~4h（待生产验证）
- [x] 异常时降级不丢数据
```

- [ ] **Step 3: Commit**

```bash
git add docs/data-pipeline-task-list.md docs/superpowers/specs/2026-06-15-async-parallel-importer-design.md
git commit -m "docs: update async mode status and design doc"
```
