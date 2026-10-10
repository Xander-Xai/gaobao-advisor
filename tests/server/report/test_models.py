from datetime import datetime

from server.report.models import Report


def test_report_creation():
    report = Report(
        id="test-report-123",
        session_id="session-456",
        student_name="张三",
        province="山东",
        score=600,
        subject="物理",
        interest="计算机科学与技术",
        summary="山东，600分，意向计算机，规划分析中。",
        facts=["省份：山东", "分数：600分"],
        suggestions=["推荐：山东大学（985）"],
        risks=["数据有限，建议以官方信息为准"],
        next_actions=["对比推荐院校的录取数据"],
        confidence=0.85,
        scene="gaokao",
    )
    assert report.id == "test-report-123"
    assert report.province == "山东"
    assert report.score == 600
    assert report.confidence == 0.85


def test_report_from_slots():
    slots = {
        "province": {"value": "山东", "filled": True},
        "score": {"value": "600", "filled": True},
        "subject": {"value": "物理", "filled": True},
        "interest": {"value": "计算机", "filled": True},
    }
    report = Report.from_slots("session-456", slots)
    assert report.province == "山东"
    assert report.score == 600
    assert report.session_id == "session-456"


def test_report_from_slots_accepts_score_rank():
    slots = {
        "province": {"value": "山东", "filled": True},
        "score_rank": {"value": "600分", "filled": True},
        "subject": {"value": "物理", "filled": True},
        "interest": {"value": "计算机", "filled": True},
    }
    report = Report.from_slots("session-456", slots)
    assert report.score == 600
    assert "600分" in report.summary


def test_report_to_dict():
    report = Report(
        id="test-123",
        session_id="sess-456",
        province="山东",
        score=600,
        subject="物理",
        interest="计算机",
        summary="测试摘要",
        facts=["事实1"],
        suggestions=["建议1"],
        risks=["风险1"],
        next_actions=["行动1"],
        confidence=0.9,
        scene="gaokao",
    )
    data = report.to_dict()
    assert data["province"] == "山东"
    assert data["score"] == 600
    assert data["confidence"] == 0.9
    assert "created_at" in data


def test_report_from_dict():
    data = {
        "id": "test-123",
        "session_id": "sess-456",
        "province": "山东",
        "score": 600,
        "subject": "物理",
        "interest": "计算机",
        "summary": "测试摘要",
        "facts": ["事实1"],
        "suggestions": ["建议1"],
        "risks": ["风险1"],
        "next_actions": ["行动1"],
        "confidence": 0.9,
        "scene": "gaokao",
        "created_at": datetime.now().isoformat(),
    }
    report = Report.from_dict(data)
    assert report.province == "山东"
    assert report.score == 600
