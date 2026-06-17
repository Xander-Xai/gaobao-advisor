from server.domain.schemas import StructuredPlanningCard
from server.report.generator import ReportGenerator


def test_generator_from_card():
    card = StructuredPlanningCard(
        title="高考志愿规划建议",
        summary="山东，600分，意向计算机，规划分析中。",
        scene="gaokao",
        facts=["省份：山东", "分数：600分", "选科：物理"],
        suggestions=["推荐：山东大学（985），参考线620分"],
        risks=["数据有限，建议以官方信息为准"],
        next_actions=["对比推荐院校的录取数据", "到省考试院官网核实"],
        confidence=0.85,
    )
    report = ReportGenerator.from_card(
        card=card,
        session_id="test-session",
        slots={"province": "山东", "score": "600", "subject": "物理", "interest": "计算机"},
    )
    assert report.province == "山东"
    assert report.score == 600
    assert report.confidence == 0.85
    assert len(report.facts) == 3
    assert len(report.suggestions) == 1


def test_generator_extracts_student_info():
    card = StructuredPlanningCard(title="测试", summary="测试摘要", scene="gaokao")
    report = ReportGenerator.from_card(
        card=card,
        session_id="test",
        slots={"province": "河南", "score": "580", "subject": "历史", "interest": "法学"},
    )
    assert report.province == "河南"
    assert report.score == 580
    assert report.subject == "历史"
    assert report.interest == "法学"


def test_generator_with_student_name():
    card = StructuredPlanningCard(title="测试", summary="测试", scene="gaokao")
    report = ReportGenerator.from_card(
        card=card,
        session_id="test",
        slots={"province": "山东"},
        student_name="张三",
    )
    assert report.student_name == "张三"
