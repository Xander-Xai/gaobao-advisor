"""Tests for the memory persistence node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from server.graph.nodes.memory import memory_node


@patch("server.graph.nodes.memory.save_slots")
@patch("server.graph.nodes.memory.save_message")
@patch("server.graph.nodes.memory.get_or_create_conversation")
@patch("server.graph.nodes.memory.get_session")
def test_memory_node_persists_conversation(mock_get_session, mock_create, mock_save_msg, mock_save_slots):
    """Memory node should persist user message, assistant reply, and slots."""
    mock_db = MagicMock()
    mock_get_session.return_value = mock_db

    state = {
        "session_id": "test-session-001",
        "input_text": "我是湖北考生580分",
        "reply": "你这个情况我建议……",
        "slots": {"province": "湖北", "score": "580", "subject": "物理"},
        "trace": [],
    }

    result = memory_node(state)

    mock_create.assert_called_once_with(mock_db, "test-session-001")
    assert mock_save_msg.call_count == 2
    mock_save_slots.assert_called_once_with(mock_db, "test-session-001", state["slots"])
    mock_db.close.assert_called_once()
    assert result["trace"][-1]["event"] == "persisted"


@patch("server.graph.nodes.memory.save_slots")
@patch("server.graph.nodes.memory.save_message")
@patch("server.graph.nodes.memory.get_or_create_conversation")
@patch("server.graph.nodes.memory.get_session")
def test_memory_node_handles_error(mock_get_session, mock_create, mock_save_msg, mock_save_slots):
    """Memory node should not crash on DB errors."""
    mock_db = MagicMock()
    mock_get_session.return_value = mock_db
    mock_create.side_effect = Exception("DB connection lost")

    state = {
        "session_id": "test-session-002",
        "input_text": "hello",
        "reply": "world",
        "slots": {},
        "trace": [],
    }

    result = memory_node(state)
    mock_db.close.assert_called_once()
    assert result["trace"][-1]["event"] == "persist_failed"


def test_memory_node_skips_without_session_id():
    """Memory node should skip when no session_id."""
    state = {
        "session_id": "",
        "input_text": "hello",
        "reply": "world",
        "slots": {},
        "trace": [],
    }

    result = memory_node(state)
    assert result["trace"][-1]["event"] == "skipped_no_session_id"
