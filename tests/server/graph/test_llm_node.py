"""Tests for the LLM reasoning node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from server.graph.nodes.llm_node import llm_node


def test_llm_node_returns_generated_reply():
    """LLM node should call the model and return a reply."""
    state = {
        "slots": {"province": "湖北", "score": "580", "subject": "物理"},
        "reasoning": "用户画像: 湖北考生, 580分, 物理类",
        "emotion_state": "🟢",
        "cognitive_model": "就业倒推法",
        "decision_heuristics": ["灵魂追问法", "家庭背景分流"],
        "expert_quotes": [],
        "data_query_results": {},
        "knowledge_context": "",
        "scene": "gaokao",
        "trace": [],
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="你这个情况我直接说——580分湖北物理类，你的最优解是……"))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("server.graph.nodes.llm_node._get_llm_client", return_value=mock_client):
        result = llm_node(state)

    assert "reply" in result
    assert len(result["reply"]) > 0
    assert result["trace"][-1]["node"] == "llm_reason"


def test_llm_node_falls_back_on_error():
    """LLM node should produce a fallback reply when the API call fails."""
    state = {
        "slots": {"province": "湖北", "score": "580"},
        "reasoning": "暂无足够信息",
        "emotion_state": "🟢",
        "cognitive_model": "default",
        "trace": [],
    }

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")

    with patch("server.graph.nodes.llm_node._get_llm_client", return_value=mock_client):
        result = llm_node(state)

    assert "reply" in result
    assert "暂时无法" in result["reply"] or "稍后再试" in result["reply"]
