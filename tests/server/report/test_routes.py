"""Tests for report API routes — generate, retrieve, and export."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from server.auth import create_session_token
from server.main import app

# Ensure SESSION_SECRET is set for tests
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-testing-32chars!!")


def _auth_token(session_id: str) -> str:
    """Generate a valid session token for testing."""
    return create_session_token(session_id)


@pytest.mark.asyncio
async def test_generate_report_endpoint():
    """POST /api/v1/report/generate should return 200 and a report_id."""
    session_id = "test-session-001"
    token = _auth_token(session_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/report/generate",
            json={
                "session_id": session_id,
                "student_name": "张三",
                "token": token,
            },
        )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "report_id" in data
    assert data["status"] == "completed"
    assert data["report_id"] != ""


@pytest.mark.asyncio
async def test_get_report_endpoint():
    """GET /api/v1/report/{id} should return report data with province field."""
    session_id = "test-session-002"
    token = _auth_token(session_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Generate first
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={
                "session_id": session_id,
                "student_name": "李四",
                "token": token,
            },
        )
        report_id = gen_resp.json()["report_id"]

        # Retrieve
        response = await client.get(
            f"/api/v1/report/{report_id}",
            params={"session_id": session_id, "token": token},
        )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "province" in data
    assert data["student_name"] == "李四"


@pytest.mark.asyncio
async def test_get_report_requires_session_token():
    """GET /api/v1/report/{id} should not be readable by report_id alone."""
    session_id = "test-session-auth"
    token = _auth_token(session_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={
                "session_id": session_id,
                "student_name": "鉴权测试",
                "token": token,
            },
        )
        report_id = gen_resp.json()["report_id"]

        response = await client.get(f"/api/v1/report/{report_id}")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_report_rejects_other_session_token():
    """A valid token for another session should not access this report."""
    owner_session = "test-session-owner"
    owner_token = _auth_token(owner_session)
    other_session = "test-session-other"
    other_token = _auth_token(other_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={
                "session_id": owner_session,
                "student_name": "归属测试",
                "token": owner_token,
            },
        )
        report_id = gen_resp.json()["report_id"]

        response = await client.get(
            f"/api/v1/report/{report_id}",
            params={"session_id": other_session, "token": other_token},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_report_html_endpoint():
    """GET /api/v1/report/{id}/html should return HTML containing 金榜题名."""
    session_id = "test-session-003"
    token = _auth_token(session_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Generate first
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={
                "session_id": session_id,
                "student_name": "王五",
                "token": token,
            },
        )
        report_id = gen_resp.json()["report_id"]

        # Retrieve HTML
        response = await client.get(
            f"/api/v1/report/{report_id}/html",
            params={"session_id": session_id, "token": token},
        )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "金榜题名" in response.text


@pytest.mark.asyncio
async def test_get_nonexistent_report():
    """GET /api/v1/report/{id} with nonexistent ID should return 404."""
    session_id = "test-session-missing"
    token = _auth_token(session_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/report/nonexistent-999",
            params={"session_id": session_id, "token": token},
        )
    assert response.status_code == 404
