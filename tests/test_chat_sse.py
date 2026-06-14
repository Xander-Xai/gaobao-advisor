"""Tests for the chat SSE endpoint structured card output."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from server.main import app


@pytest.mark.asyncio
async def test_chat_sse_emits_structured_card():
    """SSE response should include a structured card event with all required fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-sse-001",
                "scene": "gaokao",
                "message": "河北考生600分物理类想学计算机普通家庭想就业",
            },
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
