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
