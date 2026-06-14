"""Tests for StructuredPlanningCard schema."""

from server.domain.schemas import StructuredPlanningCard
from server.graph.nodes.structure import structure_output_node


def test_card_creation():
    """Card accepts all fields, verify values."""
    card = StructuredPlanningCard(
        title="高考志愿规划",
        summary="根据考生成绩推荐合适的院校和专业",
        scene="高考志愿填报",
        facts=["考生分数620分", "理科生", "省排名5000"],
        suggestions=["冲刺985院校", "关注热门专业"],
        risks=["专业调剂风险", "分数波动风险"],
        next_actions=["查询历年分数线", "参加高校宣讲会"],
        confidence=0.85,
    )
    assert card.title == "高考志愿规划"
    assert card.summary == "根据考生成绩推荐合适的院校和专业"
    assert card.scene == "高考志愿填报"
    assert card.facts == ["考生分数620分", "理科生", "省排名5000"]
    assert card.suggestions == ["冲刺985院校", "关注热门专业"]
    assert card.risks == ["专业调剂风险", "分数波动风险"]
    assert card.next_actions == ["查询历年分数线", "参加高校宣讲会"]
    assert card.confidence == 0.85


def test_card_defaults():
    """Card fields default to empty lists."""
    card = StructuredPlanningCard(title="测试标题", summary="测试摘要")
    assert card.scene == ""
    assert card.facts == []
    assert card.suggestions == []
    assert card.risks == []
    assert card.next_actions == []
    assert card.confidence == 0.0


def test_card_to_dict():
    """model_dump() produces clean dict."""
    card = StructuredPlanningCard(
        title="测试",
        summary="摘要",
        facts=["事实1", "事实2"],
        confidence=0.9,
    )
    result = card.model_dump()
    assert isinstance(result, dict)
    assert result["title"] == "测试"
    assert result["summary"] == "摘要"
    assert result["scene"] == ""
    assert result["facts"] == ["事实1", "事实2"]
    assert result["suggestions"] == []
    assert result["risks"] == []
    assert result["next_actions"] == []
    assert result["confidence"] == 0.9


def test_card_from_dict():
    """Card can be constructed from a dict."""
    data = {
        "title": "规划建议",
        "summary": "详细建议内容",
        "scene": "志愿填报",
        "facts": ["数据1", "数据2"],
        "suggestions": ["建议1"],
        "risks": ["风险1", "风险2"],
        "next_actions": ["行动1"],
        "confidence": 0.75,
    }
    card = StructuredPlanningCard(**data)
    assert card.title == "规划建议"
    assert card.summary == "详细建议内容"
    assert card.scene == "志愿填报"
    assert card.facts == ["数据1", "数据2"]
    assert card.suggestions == ["建议1"]
    assert card.risks == ["风险1", "风险2"]
    assert card.next_actions == ["行动1"]
    assert card.confidence == 0.75


def test_structure_output_gaokao():
    """Gaokao scene with data should produce a structured card with facts and schools."""
    state = {
        "scene": "gaokao",
        "slots": {"province": "河北", "score": "600分", "subject": "物理类"},
        "data_query_results": {
            "match_schools": [
                {"school_name": "华北电力大学", "min_score": 595, "school_level": "211"},
                {"school_name": "河北工业大学", "min_score": 580, "school_level": "211"},
            ],
            "rank_info": "位次约12000",
        },
        "reasoning": "用户画像: 河北600分物理类",
        "trace": [],
    }
    result = structure_output_node(state)
    card = result["structured_result"]
    assert card["title"] != ""
    assert card["summary"] != ""
    assert card["scene"] == "gaokao"
    assert len(card["facts"]) > 0
    assert len(card["suggestions"]) > 0


def test_structure_output_incomplete():
    """When data is empty, card should still have title and empty lists."""
    state = {
        "scene": "gaokao",
        "slots": {},
        "data_query_results": {},
        "reasoning": "",
        "trace": [],
    }
    result = structure_output_node(state)
    card = result["structured_result"]
    assert card["title"] != ""
    assert isinstance(card["facts"], list)
    assert isinstance(card["risks"], list)


def test_structure_output_appends_trace():
    """Node should append to trace."""
    state = {"scene": "gaokao", "slots": {}, "data_query_results": {}, "reasoning": "", "trace": []}
    result = structure_output_node(state)
    assert len(result["trace"]) > 0
    assert result["trace"][-1]["node"] == "structure_output"
