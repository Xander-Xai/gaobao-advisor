"""Regression tests for the chat pre-generation/stream/post-generation split."""

import json

import pytest

from server.routes import chat as chat_route


class _FakeGraph:
    def __init__(self, result: dict):
        self._result = result

    def invoke(self, state: dict) -> dict:
        merged = dict(state)
        merged.update(self._result)
        return merged


def _parse_sse(chunks: list[str]) -> list[dict]:
    events: list[dict] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_complete_profile_enters_llm_stream_before_post_generation(monkeypatch):
    """A prepared complete-profile state must stream the LLM and only then run post-processing."""
    graph_result = {
        "slots": {
            "province": "河北",
            "score": 600,
            "subject": "物理",
            "interest": "计算机",
        },
        "structured_result": {
            "title": "志愿分析",
            "facts": [],
            "suggestions": [],
            "risks": [],
            "next_actions": [],
        },
        "trace": [],
    }
    monkeypatch.setattr(chat_route, "get_advisor_graph", lambda: _FakeGraph(graph_result))
    monkeypatch.setattr(chat_route, "_load_persisted_state", lambda _session_id: ({}, {}))

    stream_calls: list[dict] = []

    def fake_llm_stream(state: dict):
        stream_calls.append(state)
        yield "这是LLM", False
        yield "生成回答。", False

    monkeypatch.setattr(chat_route, "llm_node_stream", fake_llm_stream)

    post_replies: list[str] = []

    async def fake_post_generation(state: dict) -> dict:
        post_replies.append(state["reply"])
        result = dict(state)
        result["quality_grade"] = "pass"
        return result

    monkeypatch.setattr(chat_route, "_run_post_generation", fake_post_generation)

    chunks = [
        chunk
        async for chunk in chat_route._sse_generator(
            "test-stream-001",
            "gaokao",
            "河北考生600分物理类想学计算机",
            None,
        )
    ]
    events = _parse_sse(chunks)

    token_text = "".join(event["content"] for event in events if event.get("type") == "token")
    assert len(stream_calls) == 1
    assert "这是LLM生成回答。" in token_text
    assert "声明：以上分析基于" in token_text
    assert len(post_replies) == 1
    assert "这是LLM生成回答。" in post_replies[0]
    assert "声明：以上分析基于" in post_replies[0]
    assert any(event.get("type") == "quality" for event in events)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_direct_question_reply_bypasses_llm_stream(monkeypatch):
    """Profile questions and other direct replies must not invoke the main LLM stream."""
    graph_result = {
        "slots": {"province": "河北"},
        "reply": "请告诉我你的高考分数。",
        "missing_fields": ["score_rank"],
        "trace": [],
    }
    monkeypatch.setattr(chat_route, "get_advisor_graph", lambda: _FakeGraph(graph_result))
    monkeypatch.setattr(chat_route, "_load_persisted_state", lambda _session_id: ({}, {}))

    def fail_if_streamed(_state: dict):
        raise AssertionError("direct reply must not call llm_node_stream")
        yield "", False

    monkeypatch.setattr(chat_route, "llm_node_stream", fail_if_streamed)

    async def fake_post_generation(state: dict) -> dict:
        return dict(state)

    monkeypatch.setattr(chat_route, "_run_post_generation", fake_post_generation)

    chunks = [
        chunk
        async for chunk in chat_route._sse_generator(
            "test-stream-002",
            "gaokao",
            "我是河北考生",
            None,
        )
    ]
    events = _parse_sse(chunks)
    token_text = "".join(event["content"] for event in events if event.get("type") == "token")

    assert "请告诉我你的高考分数。" in token_text
    assert events[-1]["type"] == "done"
