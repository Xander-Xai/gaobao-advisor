"""Tests for auth integration in chat and profile endpoints."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import ASGITransport, AsyncClient

from server.main import app


class _FakeGraph:
    def invoke(self, state):
        return {
            "session_id": state["session_id"],
            "reply": "请补充你的省份和分数。",
            "slots": {"scene": state["scene"]},
        }


class TestChatTokenIssuance:
    @pytest.mark.asyncio
    async def test_chat_returns_session_token_in_done_event(self, monkeypatch):
        """Chat SSE response should include a session_token in the done event."""
        from server.auth import create_session_token

        monkeypatch.setattr("server.routes.chat.get_advisor_graph", lambda: _FakeGraph())
        token = create_session_token("test-auth-001")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            response = await async_client.post(
                "/api/v1/chat",
                json={
                    "session_id": "test-auth-001",
                    "message": "你好",
                    "scene": "gaokao",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        done_events = [event for event in events if event.get("type") == "done"]

        assert len(done_events) == 1
        assert "session_token" in done_events[0]


class TestProfileAuth:
    @pytest.mark.asyncio
    async def test_profile_without_token_returns_401(self):
        """Profile GET without token should return 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            response = await async_client.get("/api/v1/profile/test-auth-001")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_profile_with_valid_token_returns_200(self):
        """Profile GET with valid token should return 200."""
        from server.auth import create_session_token

        token = create_session_token("test-auth-001")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            response = await async_client.get(
                "/api/v1/profile/test-auth-001",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_profile_with_invalid_token_returns_401(self):
        """Profile GET with invalid token should return 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            response = await async_client.get(
                "/api/v1/profile/test-auth-001",
                headers={"Authorization": "Bearer invalid-token-xxx"},
            )
        assert response.status_code == 401
