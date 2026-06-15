"""Verify _maybe_trim logging bug fix (C1/P17)."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.graph.nodes.llm_node import _maybe_trim


def test_maybe_trim_does_not_crash(caplog):
    """_maybe_trim should not raise TypeError when trimming messages."""
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    # Create more messages than MAX_HISTORY_ROUNDS * 2 (40)
    user_msgs = [{"role": "user", "content": f"Message {i}"} for i in range(50)]
    messages = [system_msg] + user_msgs

    with caplog.at_level(logging.INFO):
        result = _maybe_trim(messages)

    # Should have system + 40 trimmed messages
    assert len(result) == 41  # 1 system + 40 kept
    assert result[0]["role"] == "system"
    # Should NOT have TypeError in logs
    assert "TypeError" not in caplog.text


def test_maybe_trim_no_op_under_limit():
    """_maybe_trim should not modify messages under the limit."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = _maybe_trim(messages)
    assert len(result) == 3
