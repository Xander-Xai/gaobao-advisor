"""Tests for the chat SSE endpoint structured card output."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from server.auth import create_session_token
from server.main import app


@pytest.mark.asyncio
async def test_chat_sse_emits_structured_card():
    """SSE response should include a structured card event with all required fields."""
    token = create_session_token("test-sse-001")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-sse-001",
                "scene": "gaokao",
                "message": "河北考生600分物理类想学计算机普通家庭想就业",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse SSE events from the response body
    lines = response.text.split("\n")
    events = [line for line in lines if line.startswith("data: ")]
    assert len(events) > 0, "Expected at least one SSE data event"

    # Find the structured card event
    structured_found = False
    for event in events:
        payload = json.loads(event[len("data: ") :])
        if payload.get("type") == "structured":
            structured_found = True
            result = payload.get("result", {})
            assert "title" in result, "Structured card missing 'title'"
            assert "facts" in result, "Structured card missing 'facts'"
            assert "suggestions" in result, "Structured card missing 'suggestions'"
            assert "risks" in result, "Structured card missing 'risks'"
            assert "next_actions" in result, "Structured card missing 'next_actions'"
            break
    assert structured_found, "No structured card event found in SSE response"


@pytest.mark.asyncio
async def test_chat_sse_reports_no_evidence_distinctly(monkeypatch):
    """A healthy corpus with no match must stream rag_status=NO_EVIDENCE.

    NO_EVIDENCE is deliberately distinct from RAG_DISABLED/RAG_ERROR so the
    client can tell "nothing relevant" apart from "retrieval is broken". The
    graph is stubbed so the streaming contract is tested independently of
    intent routing.
    """

    class _NoEvidenceGraph:
        def invoke(self, state):
            return {
                "session_id": state["session_id"],
                "reply": "暂无匹配证据。",
                "reply_source": "template",
                "rag_state": "RAG_ENABLED",
                "rag_sources": [],
                "rag_reason": "corpus is available but holds no matching evidence",
            }

    monkeypatch.setattr("server.routes.chat.get_advisor_graph", lambda: _NoEvidenceGraph())
    token = create_session_token("test-sse-noev")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"session_id": "test-sse-noev", "scene": "gaokao", "message": "平行志愿的量子缠结规则"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    events = [json.loads(line[len("data: ") :]) for line in response.text.split("\n") if line.startswith("data: ")]
    rag_statuses = [e for e in events if e.get("type") == "rag_status"]
    assert any(e.get("state") == "NO_EVIDENCE" for e in rag_statuses), rag_statuses
