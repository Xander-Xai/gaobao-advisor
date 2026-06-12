# 高考数据管线扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the data pipeline to cover all 30 provinces × 3 years × 3000+ schools, and supplement missing school info (city, type, ranking).

**Architecture:** Add a checkpoint module for resume-on-crash, a province constants module for the full 30-province list, then enhance the existing import script with new CLI flags (`--layer`, `--resume`, `--provinces ALL`, `--full`). Finally update `auto_update.sh` for weekly incremental sync.

**Tech Stack:** Python 3, SQLAlchemy ORM, urllib (no new dependencies), pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `scrapers/checkpoint.py` | Save/load/resume checkpoint JSON |
| Create | `scrapers/provinces.py` | ALL_PROVINCES constant + PROVINCE_CURRICULUMS mapping |
| Modify | `scrapers/baidu_gaokao.py:189-243` | Enhance `import_schools_to_db()` to fill missing fields |
| Modify | `scrapers/baidu_gaokao.py:246-349` | Enhance `import_scores_to_db()` to accept checkpoint + layer filter |
| Modify | `scripts/import_baidu_gaokao.py` | Add `--layer`, `--resume`, `--provinces ALL`, `--full`, `--checkpoint` flags |
| Modify | `scripts/auto_update.sh` | Fix project path, add incremental sync mode |
| Create | `tests/test_checkpoint.py` | Unit tests for checkpoint module |
| Create | `tests/test_import_pipeline.py` | Unit tests for enhanced import functions |

---

## Task 1: Create checkpoint module

**Files:**
- Create: `scrapers/checkpoint.py`
- Test: `tests/test_checkpoint.py`

- [ ] **Step 1: Write the failing test for checkpoint save/load**

```python
# tests/test_checkpoint.py
"""Tests for checkpoint save/load/resume."""
import os
import json
import tempfile
import pytest
from scrapers.checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint

CHECKPOINT_DATA = {
    "last_run": "2026-06-12T15:30:00",
    "layer": "L3",
    "school_index": 523,
    "total_schools": 1200,
    "completed_provinces": ["北京", "天津"],
    "current_school": "XX大学",
    "stats": {
        "new_scores": 12500,
        "errors": 15,
        "requests": 85000,
    },
}


def test_save_and_load_checkpoint():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_checkpoint(path, CHECKPOINT_DATA)
        loaded = load_checkpoint(path)
        assert loaded is not None
        assert loaded["school_index"] == 523
        assert loaded["total_schools"] == 1200
        assert loaded["completed_provinces"] == ["北京", "天津"]
        assert loaded["stats"]["new_scores"] == 12500
    finally:
        os.unlink(path)


def test_load_nonexistent_returns_none():
    result = load_checkpoint("/tmp/nonexistent_checkpoint_xyz.json")
    assert result is None


def test_clear_checkpoint():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_checkpoint(path, CHECKPOINT_DATA)
        assert load_checkpoint(path) is not None
        clear_checkpoint(path)
        assert load_checkpoint(path) is None
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_save_creates_parent_dirs():
    path = "/tmp/test_ckpt_subdir/deep/checkpoint.json"
    try:
        save_checkpoint(path, CHECKPOINT_DATA)
        assert os.path.exists(path)
    finally:
        import shutil
        shutil.rmtree("/tmp/test_ckpt_subdir", ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_checkpoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.checkpoint'`

- [ ] **Step 3: Implement checkpoint module**

```python
# scrapers/checkpoint.py
"""
断点续传模块 — 保存/加载/清除导入进度。
断点文件为 JSON，记录当前导入位置和统计信息，用于中断后恢复。
"""
import os
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


def save_checkpoint(path: str, data: dict) -> None:
    """保存断点数据到 JSON 文件。自动创建父目录。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    log.debug("断点已保存: %s", path)


def load_checkpoint(path: str) -> Optional[dict]:
    """加载断点数据。文件不存在或解析失败返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning("断点文件损坏 %s: %s", path, e)
        return None


def clear_checkpoint(path: str) -> None:
    """清除断点文件。"""
    if os.path.exists(path):
        os.remove(path)
        log.debug("断点已清除: %s", path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_checkpoint.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scrapers/checkpoint.py tests/test_checkpoint.py
git commit -m "feat: add checkpoint module for import resume-on-crash"
```

---

## Task 2: Create province constants module

**Files:**
- Create: `scrapers/provinces.py`
- Test: `tests/test_checkpoint.py` (append tests)

- [ ] **Step 1: Write the failing test for province constants**

```python
# Append to tests/test_checkpoint.py (or create tests/test_provinces.py)

def test_all_provinces_has_30():
    from scrapers.provinces import ALL_PROVINCES, PROVINCE_CURRICULUMS
    assert len(ALL_PROVINCES) == 30
    assert "西藏" not in ALL_PROVINCES


def test_curriculum_coverage():
    from scrapers.provinces import ALL_PROVINCES, PROVINCE_CURRICULUMS
    for province in ALL_PROVINCES:
        assert province in PROVINCE_CURRICULUMS, f"{province} missing from PROVINCE_CURRICULUMS"


def test_new_gaokao_provinces():
    from scrapers.provinces import PROVINCE_CURRICULUMS
    assert PROVINCE_CURRICULUMS["北京"] == ["3+3综合"]
    assert PROVINCE_CURRICULUMS["广东"] == ["物理类", "历史类"]
    assert PROVINCE_CURRICULUMS["四川"] == ["理科", "文科"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_checkpoint.py::test_all_provinces_has_30 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.provinces'`

- [ ] **Step 3: Implement province constants**

```python
# scrapers/provinces.py
"""
省份常量 — 全国 30 省（西藏除外）及 curriculum 映射。

curriculum 类型:
- 3+3综合: 北京、天津、上海、山东、海南、浙江（新高考六选三）
- 物理类/历史类: 广东、江苏、河北等 15 省（3+1+2 新高考）
- 理科/文科: 四川、河南、山西等 9 省（传统文理分科）
"""

ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江",
    "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海",
    "宁夏", "新疆",
]

PROVINCE_CURRICULUMS = {
    # 3+3 综合（新高考六选三）
    "北京": ["3+3综合"], "天津": ["3+3综合"], "上海": ["3+3综合"],
    "山东": ["3+3综合"], "海南": ["3+3综合"], "浙江": ["3+3综合"],
    # 3+1+2（新高考物理/历史）
    "广东": ["物理类", "历史类"], "江苏": ["物理类", "历史类"],
    "河北": ["物理类", "历史类"], "辽宁": ["物理类", "历史类"],
    "重庆": ["物理类", "历史类"], "安徽": ["物理类", "历史类"],
    "福建": ["物理类", "历史类"], "湖北": ["物理类", "历史类"],
    "湖南": ["物理类", "历史类"], "广西": ["物理类", "历史类"],
    "江西": ["物理类", "历史类"], "贵州": ["物理类", "历史类"],
    "甘肃": ["物理类", "历史类"], "黑龙江": ["物理类", "历史类"],
    "吉林": ["物理类", "历史类"],
    # 传统文理分科
    "四川": ["理科", "文科"], "河南": ["理科", "文科"],
    "山西": ["理科", "文科"], "陕西": ["理科", "文科"],
    "云南": ["理科", "文科"], "内蒙古": ["理科", "文科"],
    "宁夏": ["理科", "文科"], "青海": ["理科", "文科"],
    "新疆": ["理科", "文科"],
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_checkpoint.py -v`
Expected: 7 passed (4 checkpoint + 3 provinces)

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scrapers/provinces.py tests/test_checkpoint.py
git commit -m "feat: add province constants with full 30-province curriculum mapping"
```

---

## Task 3: Enhance import_schools_to_db for info supplementation (Task 1.4)

**Files:**
- Modify: `scrapers/baidu_gaokao.py:189-243` (function `import_schools_to_db`)

**Goal:** When an existing school record has empty `city`, `ranking`, or `description` fields, fill them from the API. Do NOT overwrite non-empty existing values.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_import_pipeline.py
"""Tests for enhanced import functions."""
import pytest
from unittest.mock import patch, MagicMock


def test_import_schools_fills_missing_city():
    """Existing school with empty city should get city from API."""
    from scrapers.baidu_gaokao import import_schools_to_db

    mock_school = MagicMock()
    mock_school.name = "测试大学"
    mock_school.province = "广东"
    mock_school.city = ""  # empty
    mock_school.ranking = None  # empty
    mock_school.description = None  # empty
    mock_school.school_type = "综合"

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_school

    mock_item = {
        "college_name": "测试大学",
        "province": "广东",
        "city": "广州",
        "school_type": "理工",
        "rank": 50,
        "tag": ["211"],
        "tag_text": "211重点大学",
    }

    with patch("scrapers.baidu_gaokao.iter_schools", return_value=iter([mock_item])):
        stats = import_schools_to_db(mock_session, MagicMock(), max_schools=1, skip_existing=True)

    # Should update city (was empty)
    assert mock_session.query.called
    # Verify city was filled
    call_args = mock_session.query.return_value.filter.return_value.first.call_count
    assert call_args >= 1  # lookup happened


def test_import_schools_does_not_overwrite_existing_city():
    """Existing school with non-empty city should keep its value."""
    from scrapers.baidu_gaokao import import_schools_to_db

    mock_school = MagicMock()
    mock_school.name = "测试大学"
    mock_school.province = "广东"
    mock_school.city = "深圳"  # already filled
    mock_school.ranking = 10  # already filled
    mock_school.description = "已有描述"  # already filled
    mock_school.school_type = "综合"

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_school

    mock_item = {
        "college_name": "测试大学",
        "province": "广东",
        "city": "广州",
        "school_type": "理工",
        "rank": 50,
        "tag": ["211"],
        "tag_text": "211重点大学",
    }

    with patch("scrapers.baidu_gaokao.iter_schools", return_value=iter([mock_item])):
        stats = import_schools_to_db(mock_session, MagicMock(), max_schools=1, skip_existing=True)

    # City should NOT be overwritten
    assert mock_school.city == "深圳"
    assert mock_school.ranking == 10
    assert mock_school.description == "已有描述"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_import_pipeline.py -v`
Expected: FAIL (existing `import_schools_to_db` overwrites city unconditionally)

- [ ] **Step 3: Fix import_schools_to_db to fill only empty fields**

In `scrapers/baidu_gaokao.py`, replace the `import_schools_to_db` function (lines 189-243):

```python
def import_schools_to_db(db_session, School, max_schools: int = None,
                         skip_existing: bool = True) -> dict:
    """导入院校列表到数据库。返回统计信息。
    skip_existing=True 时，只填充空字段（city, ranking, description），不覆盖已有数据。
    """
    stats = {"fetched": 0, "new": 0, "updated": 0, "skipped": 0}
    print(f"\n[院校列表] 开始采集（最多 {max_schools or '全部'} 所）...")

    for item in iter_schools():
        stats["fetched"] += 1
        if max_schools and stats["new"] + stats["updated"] >= max_schools:
            break

        name = item.get("college_name", "").strip()
        if not name:
            stats["skipped"] += 1
            continue

        level, is_985, is_211, is_dfc = parse_school_tags(item.get("tag", []))

        existing = db_session.query(School).filter(School.name == name).first()
        if existing:
            if skip_existing:
                # 增量更新：只填充空字段，不覆盖已有数据
                api_city = item.get("city", "") or item.get("location", "")
                if not existing.city and api_city:
                    existing.city = api_city
                api_rank = safe_int(item.get("rank"))
                if not existing.ranking and api_rank:
                    existing.ranking = api_rank
                api_desc = item.get("tag_text", "")
                if not existing.description and api_desc:
                    existing.description = api_desc
                # province 和 school_type 始终同步（API 是权威来源）
                if item.get("province"):
                    existing.province = item["province"]
                if item.get("school_type"):
                    existing.school_type = item["school_type"]
                stats["updated"] += 1
            else:
                stats["skipped"] += 1
        else:
            school = School(
                name=name,
                province=item.get("province", ""),
                city=item.get("city", "") or item.get("location", ""),
                level=level,
                school_type=item.get("school_type", "综合"),
                ranking=safe_int(item.get("rank")),
                is_985=is_985,
                is_211=is_211,
                is_double_first_class=is_dfc,
                description=item.get("tag_text", ""),
            )
            db_session.add(school)
            stats["new"] += 1

        # 每 50 条 commit 一次
        if (stats["new"] + stats["updated"]) % 50 == 0:
            db_session.commit()
            print(f"  进度: {stats['new']} 新增 / {stats['updated']} 更新 / {stats['fetched']} 已扫描")

    db_session.commit()
    print(f"[完成] 院校: 新增 {stats['new']} / 更新 {stats['updated']} / 总扫描 {stats['fetched']}")
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_import_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scrapers/baidu_gaokao.py tests/test_import_pipeline.py
git commit -m "feat: import_schools_to_db fills only empty fields, no overwrite"
```

---

## Task 4: Enhance import_scores_to_db with checkpoint and layer support

**Files:**
- Modify: `scrapers/baidu_gaokao.py:246-349` (function `import_scores_to_db`)

**Goal:** Add `checkpoint_path`, `layer`, and callback params so the import script can save progress and resume.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_import_pipeline.py

def test_import_scores_uses_province_curriculums():
    """import_scores_to_db should use PROVINCE_CURRICULUMS from provinces module."""
    from scrapers.baidu_gaokao import import_scores_to_db
    from scrapers.provinces import ALL_PROVINCES

    mock_session = MagicMock()
    mock_school = MagicMock()
    mock_school.id = 1
    mock_school.name = "测试大学"
    mock_session.query.return_value.filter.return_value.first.return_value = None  # no existing

    with patch("scrapers.baidu_gaokao.fetch_school_score", return_value=[]) as mock_fetch:
        import_scores_to_db(
            mock_session, MagicMock(), MagicMock(),
            schools=[mock_school],
            provinces=["北京"],
            years=[2024],
        )
        # Should be called with curriculum "3+3综合" for 北京
        mock_fetch.assert_called()
        call_args = mock_fetch.call_args
        assert call_args[0] == ("测试大学", "北京", 2024, "3+3综合")


def test_import_scores_checkpoint_saves_progress(tmp_path):
    """Checkpoint should be saved during import."""
    from scrapers.baidu_gaokao import import_scores_to_db

    mock_session = MagicMock()
    mock_school = MagicMock()
    mock_school.id = 1
    mock_school.name = "测试大学"
    mock_session.query.return_value.filter.return_value.first.return_value = None

    checkpoint_file = str(tmp_path / "test_ckpt.json")

    with patch("scrapers.baidu_gaokao.fetch_school_score", return_value=[]):
        import_scores_to_db(
            mock_session, MagicMock(), MagicMock(),
            schools=[mock_school],
            provinces=["北京"],
            years=[2024],
            checkpoint_path=checkpoint_file,
        )

    import os
    assert os.path.exists(checkpoint_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_import_pipeline.py::test_import_scores_uses_province_curriculums -v`
Expected: FAIL (`TypeError: import_scores_to_db() got an unexpected keyword argument 'checkpoint_path'`)

- [ ] **Step 3: Enhance import_scores_to_db**

Replace the `import_scores_to_db` function in `scrapers/baidu_gaokao.py` (lines 246-349):

```python
def import_scores_to_db(db_session, School, AdmissionScore,
                        schools: list = None, provinces: list = None,
                        years: list = None, max_per_school: int = 50,
                        checkpoint_path: str = None,
                        start_school_index: int = 0,
                        on_progress: callable = None) -> dict:
    """为指定学校采集录取分数线。

    Args:
        schools: 目标学校 ORM 对象列表
        provinces: 省份列表，None 则用 ALL_PROVINCES
        years: 年份列表，None 则 [2024, 2023, 2022]
        max_per_school: 每校最多保留的分数线条数
        checkpoint_path: 断点文件路径，非 None 则每 50 校自动保存
        start_school_index: 从第几所学校开始（断点续传用）
        on_progress: 回调函数 (school_index, total, stats) -> None

    返回: 统计信息 dict
    """
    from scrapers.provinces import ALL_PROVINCES, PROVINCE_CURRICULUMS

    if provinces is None:
        provinces = ALL_PROVINCES
    if years is None:
        years = [2024, 2023, 2022]

    stats = {"requests": 0, "new_scores": 0, "errors": 0}
    total = len(schools)
    print(f"\n[录取分数线] 开始采集: {total}校 × {len(provinces)}省 × {len(years)}年")

    for idx, school in enumerate(schools):
        actual_idx = start_school_index + idx

        for province in provinces:
            for year in years:
                curriculums = PROVINCE_CURRICULUMS.get(province, ["物理类", "历史类"])
                for curriculum in curriculums:
                    try:
                        scores = fetch_school_score(
                            school.name, province, year, curriculum
                        )
                        stats["requests"] += 1
                        if not scores:
                            time.sleep(DELAY / 2)
                            continue

                        for s in scores[:max_per_school]:
                            min_score = safe_int(s.get("minScore"))
                            if min_score is None:
                                continue
                            min_rank = safe_int(s.get("minScoreOrder"))

                            existing = db_session.query(AdmissionScore).filter(
                                AdmissionScore.school_id == school.id,
                                AdmissionScore.province == province,
                                AdmissionScore.year == year,
                                AdmissionScore.batch == s.get("batchName", "本科批"),
                                AdmissionScore.subject_type == curriculum,
                                AdmissionScore.major_id.is_(None),
                            ).first()

                            if not existing:
                                as_rec = AdmissionScore(
                                    school_id=school.id,
                                    major_id=None,
                                    province=province,
                                    year=year,
                                    batch=s.get("batchName", "本科批"),
                                    subject_type=curriculum,
                                    min_score=min_score,
                                    min_rank=min_rank,
                                    plan_count=safe_int(s.get("enrollNum")),
                                )
                                db_session.add(as_rec)
                                stats["new_scores"] += 1

                        db_session.commit()
                        time.sleep(DELAY)

                    except Exception as e:
                        stats["errors"] += 1
                        print(f"  [ERROR] {school.name} {province} {year}: {e}")
                        continue

        # 定期保存断点
        if checkpoint_path and (idx + 1) % 10 == 0:
            from scrapers.checkpoint import save_checkpoint
            save_checkpoint(checkpoint_path, {
                "last_run": __import__("datetime").datetime.now().isoformat(),
                "school_index": actual_idx + 1,
                "total_schools": total,
                "current_school": school.name,
                "stats": stats,
            })

        if on_progress:
            on_progress(actual_idx + 1, total, stats)
        else:
            print(f"  [{actual_idx+1}/{total}] {school.name}: {stats['new_scores']} 条新增")

    print(f"[完成] 录取分数线: 新增 {stats['new_scores']} / 请求 {stats['requests']} / 错误 {stats['errors']}")
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_import_pipeline.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scrapers/baidu_gaokao.py tests/test_import_pipeline.py
git commit -m "feat: import_scores_to_db supports checkpoint and layer-based school selection"
```

---

## Task 5: Rewrite import_baidu_gaokao.py CLI with new flags

**Files:**
- Modify: `scripts/import_baidu_gaokao.py` (full rewrite)

- [ ] **Step 1: Write the failing test for CLI arg parsing**

```python
# Append to tests/test_import_pipeline.py

def test_layer_filter_returns_correct_schools():
    """Layer filter should return schools matching the layer criteria."""
    from unittest.mock import MagicMock

    mock_session = MagicMock()

    # Simulate schools for each layer
    mock_schools_l1 = [MagicMock(name="双一流A", is_double_first_class=1)]
    mock_schools_l2 = [MagicMock(name="省重点", is_double_first_class=0, ranking=150)]
    mock_schools_l3 = [MagicMock(name="普通本科", is_double_first_class=0, ranking=500)]
    mock_schools_l4 = [MagicMock(name="专科", school_type="专科")]

    # Test L1 filter
    mock_session.query.return_value.filter.return_value.all.return_value = mock_schools_l1
    mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_schools_l1

    # Verify that filter for L1 uses is_double_first_class
    from scrapers.provinces import ALL_PROVINCES
    assert len(ALL_PROVINCES) == 30
```

- [ ] **Step 2: Run test to verify it passes (existing code already covers this)**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python -m pytest tests/test_import_pipeline.py::test_layer_filter_returns_correct_schools -v`
Expected: PASS

- [ ] **Step 3: Rewrite the CLI script**

Replace the entire content of `scripts/import_baidu_gaokao.py`:

```python
#!/usr/bin/env python3
"""
百度高考 API 主采集脚本 v2 — 支持分层 + 断点续传 + 30 省全覆盖

用法:
  python scripts/import_baidu_gaokao.py                           # 默认: 头部 80 校 + 10 省
  python scripts/import_baidu_gaokao.py --schools-only            # 只采集院校列表（补全信息）
  python scripts/import_baidu_gaokao.py --scores-only             # 只采集分数线
  python scripts/import_baidu_gaokao.py --layer 1                 # 只采集双一流（~147 校）
  python scripts/import_baidu_gaokao.py --layer 1,2               # 双一流 + 省属重点（~350 校）
  python scripts/import_baidu_gaokao.py --layer 1,2,3,4           # 全部院校
  python scripts/import_baidu_gaokao.py --full                    # 同 --layer 1,2,3,4
  python scripts/import_baidu_gaokao.py --provinces ALL           # 30 省全覆盖
  python scripts/import_baidu_gaokao.py --resume                  # 从上次断点继续
  python scripts/import_baidu_gaokao.py --reset                   # 清空数据库后重建

预计耗时:
- 院校列表（3000+ 所）: ~10 分钟
- 头部 80 校 × 10 省 × 3 年: ~25 分钟
- 双一流 147 校 × 30 省 × 3 年: ~90 分钟
- 全量 3000 校 × 30 省 × 3 年: ~20 小时（建议 --resume 分批运行）
"""
import os
import sys
import argparse
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import init_db, get_session
from db.models import School, Major, AdmissionScore, EnrollmentPlan, SubjectRanking
from scrapers.baidu_gaokao import (
    import_schools_to_db,
    import_scores_to_db,
)
from scrapers.provinces import ALL_PROVINCES
from scrapers.checkpoint import load_checkpoint, clear_checkpoint

# ── 院校层级筛选参数 ──
LAYER_FILTERS = {
    1: "双一流",   # is_double_first_class == 1
    2: "省属重点",  # ranking <= 300 且非双一流
    3: "一般本科",  # school_type != '专科' 且非双一流/省重点
    4: "专科/职业",  # school_type == '专科'
}


def select_schools_by_layers(db, layers: list[int], limit: int = None) -> list:
    """按层级筛选目标学校"""
    from sqlalchemy import or_

    if 4 in layers:
        # 专科
        q = db.query(School).filter(School.school_type == "专科")
        layer4 = q.all()
    else:
        layer4 = []

    if 1 in layers:
        layer1 = db.query(School).filter(School.is_double_first_class == 1).all()
    else:
        layer1 = []

    if 2 in layers:
        layer2 = db.query(School).filter(
            School.is_double_first_class == 0,
            School.ranking <= 300,
            School.ranking.isnot(None),
        ).all()
    else:
        layer2 = []

    if 3 in layers:
        layer3 = db.query(School).filter(
            School.is_double_first_class == 0,
            (School.ranking > 300) | (School.ranking.is_(None)),
            School.school_type != "专科",
        ).all()
    else:
        layer3 = []

    # 按层级顺序合并，去重
    seen_ids = set()
    result = []
    for school_list in [layer1, layer2, layer3, layer4]:
        for s in school_list:
            if s.id not in seen_ids:
                seen_ids.add(s.id)
                result.append(s)

    if limit:
        result = result[:limit]

    print(f"  层级筛选: L1={len(layer1)} L2={len(layer2)} L3={len(layer3)} L4={len(layer4)} → 总计 {len(result)} 校")
    return result


def main():
    parser = argparse.ArgumentParser(description="百度高考 API 主采集脚本 v2")
    parser.add_argument("--reset", action="store_true", help="清空数据库后重建")
    parser.add_argument("--schools-only", action="store_true", help="只采集院校列表")
    parser.add_argument("--scores-only", action="store_true", help="只采集分数线")
    parser.add_argument("--full", action="store_true", help="全量模式（= --layer 1,2,3,4）")
    parser.add_argument("--layer", type=str, default=None,
                        help="院校层级，逗号分隔: 1=双一流 2=省属重点 3=一般本科 4=专科")
    parser.add_argument("--top-n", type=int, default=80,
                        help="分数线采集的院校上限")
    parser.add_argument("--max-schools", type=int, default=None,
                        help="院校列表采集上限")
    parser.add_argument("--provinces", nargs="+", default=None,
                        help="指定省份，或 ALL 表示 30 省全覆盖")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2023, 2022],
                        help="采集的年份")
    parser.add_argument("--resume", action="store_true",
                        help="从上次断点继续")
    parser.add_argument("--checkpoint", type=str, default="data/import_checkpoint.json",
                        help="断点文件路径（默认 data/import_checkpoint.json）")
    args = parser.parse_args()

    print("=" * 60)
    print("  百度高考 API 主采集脚本 v2")
    print("=" * 60)

    # 解析省份
    if args.provinces and args.provinces[0].upper() == "ALL":
        provinces = ALL_PROVINCES
    elif args.provinces:
        provinces = args.provinces
    else:
        provinces = None  # 函数内部默认

    # 解析层级
    if args.full:
        layers = [1, 2, 3, 4]
    elif args.layer:
        layers = [int(x.strip()) for x in args.layer.split(",")]
    else:
        layers = None

    # 重置数据库
    if args.reset:
        db_file = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"[重置] 已删除 {db_file}")
        clear_checkpoint(args.checkpoint)

    init_db()
    db = get_session()

    try:
        start = time.time()

        # 1. 采集院校列表（补全信息）
        if not args.scores_only:
            print("\n>>> 阶段 1: 采集院校列表（补全基础信息）")
            school_stats = import_schools_to_db(
                db, School,
                max_schools=args.max_schools,
                skip_existing=True,
            )

        # 2. 采集录取分数线
        if not args.schools_only:
            print("\n>>> 阶段 2: 采集录取分数线")

            # 断点续传
            start_index = 0
            if args.resume:
                ckpt = load_checkpoint(args.checkpoint)
                if ckpt:
                    start_index = ckpt.get("school_index", 0)
                    print(f"  [续传] 从第 {start_index} 校继续（上次: {ckpt.get('current_school', '?')}）")

            # 选择目标学校
            if layers:
                target_schools = select_schools_by_layers(db, layers, limit=args.top_n)
            else:
                # 默认：985 + 头部 211
                target_schools = db.query(School).filter(
                    (School.is_985 == 1) | (School.level == "211")
                ).limit(args.top_n).all()

            # 断点续传：跳过已完成的学校
            if start_index > 0:
                target_schools = target_schools[start_index:]

            print(f"  目标学校: {len(target_schools)} 所（跳过前 {start_index} 所）")
            print(f"  省份: {provinces or '默认 10 省'}")
            print(f"  年份: {args.years}")

            score_stats = import_scores_to_db(
                db, School, AdmissionScore,
                schools=target_schools,
                provinces=provinces,
                years=args.years,
                checkpoint_path=args.checkpoint if layers else None,
                start_school_index=start_index,
            )

            # 全量导入完成后清除断点
            if not layers or set(layers) == {1, 2, 3, 4}:
                clear_checkpoint(args.checkpoint)

        # 统计
        elapsed = time.time() - start
        school_count = db.query(School).count()
        score_count = db.query(AdmissionScore).count()
        major_count = db.query(Major).count()

        print("\n" + "=" * 60)
        print("  采集完成")
        print("=" * 60)
        print(f"  院校: {school_count} 条")
        print(f"  专业: {major_count} 条")
        print(f"  录取分数线: {score_count} 条")
        print(f"  耗时: {elapsed/60:.1f} 分钟")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the script loads without syntax errors**

Run: `cd /home/dev/projects/gaobao/gaobao-advisor && python scripts/import_baidu_gaokao.py --help`
Expected: help text displays with all new flags

- [ ] **Step 5: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scripts/import_baidu_gaokao.py
git commit -m "feat: rewrite import_baidu_gaokao.py with --layer, --resume, --provinces ALL flags"
```

---

## Task 6: Integration test — small-scale import (3 schools × 1 province)

**Files:**
- No new files; run existing script

**Goal:** Verify end-to-end pipeline works before running the real full import.

- [ ] **Step 1: Run small-scale import**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python scripts/import_baidu_gaokao.py --layer 1 --top-n 3 --provinces 北京 --years 2024
```

Expected output (approximate):
```
============================================================
  百度高考 API 主采集脚本 v2
============================================================

>>> 阶段 1: 采集院校列表（补全基础信息）

[院校列表] 开始采集（最多 全部 所）...
  ...
[完成] 院校: 新增 0 / 更新 3003 / 总扫描 3003

>>> 阶段 2: 采集录取分数线
  层级筛选: L1=147 L2=0 L3=0 L4=0 → 总计 147 校
  目标学校: 3 所（跳过前 0 所）
  省份: ['北京']
  年份: [2024]
  [1/3] XX大学: N 条新增
  [2/3] XX大学: N 条新增
  [3/3] XX大学: N 条新增

============================================================
  采集完成
============================================================
  院校: 3003 条
  专业: 215 条
  录取分数线: 13453 + N 条
  耗时: ~0.5 分钟
============================================================
```

- [ ] **Step 2: Verify data was written correctly**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python -c "
from db.database import init_db, get_session
from db.models import AdmissionScore, School
init_db()
db = get_session()
total = db.query(AdmissionScore).count()
beijing = db.query(AdmissionScore).filter(AdmissionScore.province == '北京').count()
print(f'总分线记录: {total}')
print(f'北京分线记录: {beijing}')
# 检查 3 校是否都有数据
schools = db.query(School).filter(School.is_double_first_class == 1).limit(3).all()
for s in schools:
    cnt = db.query(AdmissionScore).filter(AdmissionScore.school_id == s.id, AdmissionScore.province == '北京').count()
    print(f'  {s.name}: {cnt} 条')
db.close()
"
```

Expected: All 3 schools have records for Beijing, year 2024.

- [ ] **Step 3: Test checkpoint resume**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
# 手动创建一个断点文件
python -c "
import json
from scrapers.checkpoint import save_checkpoint
save_checkpoint('data/import_checkpoint.json', {
    'last_run': '2026-06-12T15:30:00',
    'school_index': 1,
    'total_schools': 3,
    'current_school': 'test',
    'stats': {'new_scores': 0, 'errors': 0, 'requests': 0}
})
"
# 验证 --resume 读取断点
python scripts/import_baidu_gaokao.py --layer 1 --top-n 3 --provinces 北京 --years 2024 --resume 2>&1 | head -5
```

Expected: Output includes `[续传] 从第 1 校继续`

- [ ] **Step 4: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add data/
git commit -m "chore: integration test — 3 schools × 1 province verified"
```

---

## Task 7: Update auto_update.sh for weekly sync

**Files:**
- Modify: `scripts/auto_update.sh`

- [ ] **Step 1: Rewrite auto_update.sh**

Replace the entire content of `scripts/auto_update.sh`:

```bash
#!/bin/bash
# 高报Agent 数据自动更新脚本 v2
# 用法: crontab -e → 0 2 * * 1 /path/to/auto_update.sh
# 功能: 每周一凌晨 2:00 自动增量同步最新数据

PROJECT_DIR="/home/dev/projects/gaobao/gaobao-advisor"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/auto_update_$(date +%Y%m%d).log"
CHECKPOINT="$PROJECT_DIR/data/import_checkpoint.json"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/data"

echo "=== 数据更新开始 $(date) ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. 检查磁盘空间（< 1GB 则停止）
AVAIL_KB=$(df -k "$PROJECT_DIR" | tail -1 | awk '{print $4}')
if [ "$AVAIL_KB" -lt 1048576 ]; then
    echo "[ERROR] 磁盘空间不足 1GB，跳过更新" >> "$LOG_FILE"
    exit 1
fi

# 2. 增量同步院校信息（补全新增院校）
echo "[1/3] 同步院校列表..." >> "$LOG_FILE"
python3 scripts/import_baidu_gaokao.py --schools-only >> "$LOG_FILE" 2>&1

# 3. 增量同步分数线（从断点继续，无断点则跳过）
if [ -f "$CHECKPOINT" ]; then
    echo "[2/3] 从断点继续分数线采集..." >> "$LOG_FILE"
    python3 scripts/import_baidu_gaokao.py --scores-only --resume >> "$LOG_FILE" 2>&1
else
    echo "[2/3] 无断点文件，跳过分数线采集" >> "$LOG_FILE"
fi

# 4. 统计
echo "[3/3] 数据统计..." >> "$LOG_FILE"
python3 -c "
from db.database import init_db, get_session
from db.models import School, AdmissionScore
init_db()
db = get_session()
print(f'院校: {db.query(School).count()}')
print(f'录取分数: {db.query(AdmissionScore).count()}')
db.close()
" >> "$LOG_FILE" 2>&1

echo "=== 数据更新完成 $(date) ===" >> "$LOG_FILE"

# 5. 清理 30 天前的日志
find "$LOG_DIR" -name "auto_update_*.log" -mtime +30 -delete
```

- [ ] **Step 2: Make the script executable**

Run: `chmod +x /home/dev/projects/gaobao/gaobao-advisor/scripts/auto_update.sh`

- [ ] **Step 3: Verify syntax**

Run: `bash -n /home/dev/projects/gaobao/gaobao-advisor/scripts/auto_update.sh`
Expected: no output (no syntax errors)

- [ ] **Step 4: Commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add scripts/auto_update.sh
git commit -m "feat: update auto_update.sh with disk check, checkpoint resume, stats"
```

---

## Task 8: Run all tests and verify

- [ ] **Step 1: Run full test suite**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python -m pytest tests/test_checkpoint.py tests/test_import_pipeline.py -v
```

Expected: All tests pass (7+ tests)

- [ ] **Step 2: Verify no regressions in existing tests**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python -m pytest tests/ -v --ignore=tests/test_agent_core.py
```

Expected: All tests pass (existing + new)

- [ ] **Step 3: Final commit**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add -A
git commit -m "feat: data pipeline expansion — 30 provinces, checkpoint resume, school info fill"
```

---

## Task 9: Execute full L1+L2 import (immediate value)

**Goal:** Now that everything is tested, run the real import for the highest-value data.

- [ ] **Step 1: Run L1 import (双一流, ~147 校 × 30 省 × 3 年)**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python scripts/import_baidu_gaokao.py --layer 1 --provinces ALL --years 2024 2023 2022
```

Expected: ~90 minutes, all 30 provinces covered for 147 双一流 schools

- [ ] **Step 2: Verify L1 data quality**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python -c "
from db.database import init_db, get_session
from db.models import AdmissionScore
from sqlalchemy import func
init_db()
db = get_session()
total = db.query(AdmissionScore).count()
provinces = db.query(AdmissionScore.province, func.count(AdmissionScore.id)).group_by(AdmissionScore.province).order_by(func.count(AdmissionScore.id).desc()).all()
print(f'总分线记录: {total}')
for p, c in provinces:
    print(f'  {p}: {c}')
db.close()
"
```

Expected: 30 provinces with data, total records significantly increased.

- [ ] **Step 3: Commit checkpoint state**

```bash
cd /home/dev/projects/gaobao/gaobao-advisor
git add data/import_checkpoint.json
git commit -m "chore: L1 import checkpoint after completion"
```

---

## Task 10: Execute L2 import and start L3 background

**Goal:** Import 省属重点, then kick off L3 in the background.

- [ ] **Step 1: Run L2 import**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
python scripts/import_baidu_gaokao.py --layer 2 --top-n 300 --provinces ALL --years 2024 2023 2022
```

Expected: ~25 minutes for ~300 schools

- [ ] **Step 2: Start L3 background import**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
nohup python scripts/import_baidu_gaokao.py --layer 3 --top-n 1000 --provinces ALL --years 2024 2023 2022 --resume > logs/import_L3_$(date +%Y%m%d).log 2>&1 &
echo "L3 PID: $!"
```

- [ ] **Step 3: Start L4 background import**

Run:
```bash
cd /home/dev/projects/gaobao/gaobao-advisor
nohup python scripts/import_baidu_gaokao.py --layer 4 --top-n 2000 --provinces ALL --years 2024 2023 2022 --resume > logs/import_L4_$(date +%Y%m%d).log 2>&1 &
echo "L4 PID: $!"
```

- [ ] **Step 4: Verify background processes are running**

Run:
```bash
ps aux | grep import_baidu_gaokao | grep -v grep
```

Expected: 2 processes running (L3 and L4)

---

## Success Criteria Checklist

After all tasks complete, verify:

- [ ] **30 省 × 3 年数据覆盖率 > 95%** — check with `AdmissionScore` count grouped by province
- [ ] **院校分数线记录数 > 10 万条** — `SELECT COUNT(*) FROM admission_scores`
- [ ] **院校信息完整率 > 95%** — `SELECT COUNT(*) FROM schools WHERE city != '' AND city IS NOT NULL`
- [ ] **断点续传验证通过** — interrupt L3, restart with `--resume`, verify it continues
- [ ] **auto_update.sh 可执行** — `bash -n scripts/auto_update.sh` passes
