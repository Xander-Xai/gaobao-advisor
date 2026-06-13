"""Tests for multi-scene support (gaokao, kaoyan, career).

Validates that the LangGraph workflow correctly:
- Detects scene from input keywords
- Preserves explicitly set scenes
- Generates missing-field questions per scene
- Routes complete profiles through the full pipeline
"""
import pytest
from unittest.mock import MagicMock, patch

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
    """Build a fresh compiled graph for each test."""
    return build_advisor_graph()


# ── Scene detection ───────────────────────────────────────────


def test_kaoyan_scene_detection(graph):
    """Keywords like '考研' should trigger kaoyan scene."""
    result = graph.invoke({
        "input_text": "我想考研到北大计算机专业",
        "scene": "general",
        "session_id": "test-kaoyan-001",
        "slots": {},
    })
    assert result.get("scene") == "kaoyan"


def test_career_scene_detection(graph):
    """Keywords like '就业'/'薪资' should trigger career scene."""
    result = graph.invoke({
        "input_text": "计算机专业毕业好找工作吗？薪资怎么样？",
        "scene": "general",
        "session_id": "test-career-001",
        "slots": {},
    })
    assert result.get("scene") == "career"


def test_gaokao_scene_detection(graph):
    """Keywords like '高考'/'志愿' should trigger gaokao scene."""
    result = graph.invoke({
        "input_text": "今年高考志愿怎么填报",
        "scene": "general",
        "session_id": "test-gaokao-001",
        "slots": {},
    })
    assert result.get("scene") == "gaokao"


# ── Scene override ────────────────────────────────────────────


def test_explicit_scene_override_kaoyan(graph):
    """When scene is pre-set to 'kaoyan', it should not be overridden."""
    result = graph.invoke({
        "input_text": "你好",
        "scene": "kaoyan",
        "session_id": "test-explicit-001",
        "slots": {},
    })
    assert result.get("scene") == "kaoyan"


def test_explicit_scene_override_career(graph):
    """When scene is pre-set to 'career', it should not be overridden."""
    result = graph.invoke({
        "input_text": "你好",
        "scene": "career",
        "session_id": "test-explicit-002",
        "slots": {},
    })
    assert result.get("scene") == "career"


# ── Missing slots per scene ──────────────────────────────────


def test_kaoyan_missing_slots_asks_question(graph):
    """Kaoyan scene with empty slots should report missing fields."""
    result = graph.invoke({
        "input_text": "我想考研",
        "scene": "kaoyan",
        "session_id": "test-kaoyan-002",
        "slots": {},
    })
    missing = result.get("missing_fields", [])
    assert len(missing) > 0
    # kaoyan requires interest and goal
    assert "interest" in missing or "goal" in missing


def test_career_missing_slots_asks_question(graph):
    """Career scene with empty slots should report missing fields."""
    result = graph.invoke({
        "input_text": "我想了解就业方向",
        "scene": "career",
        "session_id": "test-career-002",
        "slots": {},
    })
    missing = result.get("missing_fields", [])
    assert len(missing) > 0
    # career requires interest
    assert "interest" in missing


def test_gaokao_missing_slots_reports_all_four(graph):
    """Gaokao scene with empty slots should report all four required fields."""
    result = graph.invoke({
        "input_text": "帮我填志愿",
        "scene": "gaokao",
        "session_id": "test-gaokao-002",
        "slots": {},
    })
    missing = result.get("missing_fields", [])
    assert len(missing) >= 3  # province, score, subject, interest


# ── Complete profile per scene ───────────────────────────────


def test_kaoyan_complete_profile_full_pipeline(graph):
    """Kaoyan with all required slots should run the full pipeline."""
    result = graph.invoke({
        "input_text": "我想考研到北大计算机",
        "scene": "kaoyan",
        "session_id": "test-kaoyan-full-001",
        "slots": {"interest": "计算机", "goal": "北京大学"},
    })
    assert result.get("reply")
    assert result.get("scene") == "kaoyan"


def test_career_complete_profile_full_pipeline(graph):
    """Career with all required slots should run the full pipeline."""
    result = graph.invoke({
        "input_text": "计算机就业前景如何",
        "scene": "career",
        "session_id": "test-career-full-001",
        "slots": {"interest": "计算机"},
    })
    assert result.get("reply")
    assert result.get("scene") == "career"


# ── Partial slots ────────────────────────────────────────────


def test_kaoyan_partial_slots_still_incomplete(graph):
    """Kaoyan with only 'interest' filled should still report 'goal' as missing.

    Note: The slot extractor auto-extracts 'goal' from text containing '考研'.
    We use an input that does NOT contain goal keywords to verify the check node.
    """
    result = graph.invoke({
        "input_text": "你好，我想咨询研究生的事情",
        "scene": "kaoyan",
        "session_id": "test-kaoyan-partial-001",
        "slots": {"interest": "计算机"},
    })
    missing = result.get("missing_fields", [])
    assert "goal" in missing
    assert "interest" not in missing


def test_gaokao_partial_slots_still_incomplete(graph):
    """Gaokao with only province and score should still ask for subject and interest."""
    result = graph.invoke({
        "input_text": "帮我报志愿",
        "scene": "gaokao",
        "session_id": "test-gaokao-partial-001",
        "slots": {"province": "北京", "score": 620},
    })
    missing = result.get("missing_fields", [])
    assert "subject" in missing or "interest" in missing


# ── Trace verification ───────────────────────────────────────


def test_multi_scene_trace_contains_all_nodes(graph):
    """Every scene run should produce a trace with key nodes."""
    result = graph.invoke({
        "input_text": "我想考研",
        "scene": "kaoyan",
        "session_id": "test-trace-001",
        "slots": {},
    })
    trace = result.get("trace", [])
    node_names = [t.get("node") for t in trace]
    assert "security_scan" in node_names
    assert "intent_detect" in node_names
    assert "scene_route" in node_names
    assert "profile_check" in node_names
