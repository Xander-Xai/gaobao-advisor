import pytest
from server.report.cover import CoverGenerator
from server.report.models import Report


def test_cover_svg_contains_title():
    report = Report(session_id="test", province="山东", score=600, subject="物理", interest="计算机", student_name="张三")
    svg = CoverGenerator.generate_svg(report)
    assert "金榜题名" in svg
    assert "张三" in svg
    assert "山东" in svg
    assert "600" in svg


def test_cover_svg_is_valid_xml():
    report = Report(session_id="test", province="山东", score=600, subject="物理", interest="计算机")
    svg = CoverGenerator.generate_svg(report)
    assert svg.startswith("<?xml")
    assert "<svg" in svg
    assert "</svg>" in svg


def test_cover_svg_without_name():
    report = Report(session_id="test", province="山东", score=600, subject="物理", interest="计算机")
    svg = CoverGenerator.generate_svg(report)
    assert "金榜题名" in svg
