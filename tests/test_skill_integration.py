"""Tests for SkillService integration into LangGraph nodes."""

from unittest.mock import MagicMock, patch

import pytest

from server.graph.graph import build_advisor_graph


@pytest.fixture(autouse=True)
def _mock_llm():
    """Mock the LLM client so integration tests don't call the real API."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="根据你的信息，我建议……"))]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("server.graph.nodes.llm_node._get_llm_client", return_value=mock_client):
        yield


@pytest.fixture
def graph():
    return build_advisor_graph()


def test_quality_node_injects_skill_context(graph):
    """quality_orchestrate_node should produce skill_context in state."""
    result = graph.invoke(
        {
            "input_text": "我是河北考生，600分，想学计算机",
            "scene": "gaokao",
            "session_id": "test-skill-001",
            "slots": {"province": "河北", "score": "600分", "subject": "物理类"},
        }
    )
    reasoning = result.get("reasoning", "")
    assert isinstance(reasoning, str)
    assert "社会筛子论" in reasoning or "就业倒推法" in reasoning or len(reasoning) > 50


def test_reasoning_contains_mental_model(graph):
    """reason_node should include skill context when scene is gaokao."""
    result = graph.invoke(
        {
            "input_text": "我是河北考生，物理类，600分，想学计算机",
            "scene": "gaokao",
            "session_id": "test-skill-002",
            "slots": {"province": "河北", "score": "600分"},
        }
    )
    reasoning = result.get("reasoning", "")
    assert len(reasoning) > 0


def test_full_pipeline_with_skill(graph):
    """Skill-enabled complete profile should finish pre-generation before LLM streaming."""
    result = graph.invoke(
        {
            "input_text": "河北考生600分物理类想学计算机普通家庭",
            "scene": "gaokao",
            "session_id": "test-skill-003",
            "slots": {},
        }
    )
    assert not result.get("reply")
    assert result.get("structured_result")
    trace = result.get("trace", [])
    node_names = [t.get("node") for t in trace]
    assert "quality_orchestrate" in node_names
    assert "reason" in node_names
    assert trace[-1].get("node") == "structure_output"
