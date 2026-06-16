import pytest
import os
import tempfile
from server.report.storage import ReportStorage
from server.report.models import Report


def test_save_and_load_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ReportStorage(base_dir=tmpdir)
        report = Report(
            id="test-123", session_id="sess-456", province="山东", score=600,
            subject="物理", interest="计算机", summary="测试摘要",
            facts=["事实1"], suggestions=["建议1"], risks=["风险1"],
            next_actions=["行动1"], confidence=0.9, scene="gaokao",
        )
        storage.save(report)
        loaded = storage.load("test-123")
        assert loaded.province == "山东"
        assert loaded.score == 600
        assert loaded.id == "test-123"


def test_load_nonexistent_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ReportStorage(base_dir=tmpdir)
        result = storage.load("nonexistent")
        assert result is None


def test_list_reports_by_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ReportStorage(base_dir=tmpdir)
        report1 = Report(id="r1", session_id="sess-a", province="山东", score=600, subject="物理", interest="计算机")
        report2 = Report(id="r2", session_id="sess-a", province="山东", score=610, subject="物理", interest="计算机")
        report3 = Report(id="r3", session_id="sess-b", province="河南", score=580, subject="历史", interest="法学")
        storage.save(report1)
        storage.save(report2)
        storage.save(report3)
        reports = storage.list_by_session("sess-a")
        assert len(reports) == 2
        assert {r.id for r in reports} == {"r1", "r2"}
