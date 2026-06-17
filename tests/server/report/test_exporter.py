from server.report.exporter import ReportExporter
from server.report.models import Report


def test_export_html():
    report = Report(
        id="test-123", session_id="sess-456", student_name="张三",
        province="山东", score=600, subject="物理", interest="计算机",
        summary="山东，600分，意向计算机",
        facts=["省份：山东", "分数：600分"],
        suggestions=["推荐：山东大学"],
        risks=["数据有限"],
        next_actions=["对比录取数据"],
        confidence=0.85, scene="gaokao",
    )
    html = ReportExporter.to_html(report)
    assert "张三" in html
    assert "山东" in html
    assert "600分" in html
    assert "山东大学" in html
    assert "<!DOCTYPE html>" in html


def test_export_html_minimal_report():
    report = Report(id="test", session_id="sess", province="山东", score=600, subject="物理", interest="计算机")
    html = ReportExporter.to_html(report)
    assert "<!DOCTYPE html>" in html
    assert "山东" in html
