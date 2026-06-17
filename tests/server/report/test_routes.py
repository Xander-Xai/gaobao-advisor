"""Tests for report API routes — generate, retrieve, and export."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.main import app


@pytest.mark.asyncio
async def test_generate_report_endpoint():
    """POST /api/v1/report/generate should return 200 and a report_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/report/generate",
            json={"session_id": "test-session-001", "student_name": "张三"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert data["status"] == "completed"
    assert data["report_id"] != ""


@pytest.mark.asyncio
async def test_get_report_endpoint():
    """GET /api/v1/report/{id} should return report data with province field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Generate first
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={"session_id": "test-session-002", "student_name": "李四"},
        )
        report_id = gen_resp.json()["report_id"]

        # Retrieve
        response = await client.get(f"/api/v1/report/{report_id}")
    assert response.status_code == 200
    data = response.json()
    assert "province" in data
    assert data["student_name"] == "李四"


@pytest.mark.asyncio
async def test_get_report_html_endpoint():
    """GET /api/v1/report/{id}/html should return HTML containing 金榜题名."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Generate first
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={"session_id": "test-session-003", "student_name": "王五"},
        )
        report_id = gen_resp.json()["report_id"]

        # Retrieve HTML
        response = await client.get(f"/api/v1/report/{report_id}/html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "金榜题名" in response.text


@pytest.mark.asyncio
async def test_get_nonexistent_report():
    """GET /api/v1/report/{id} with nonexistent ID should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/report/nonexistent-999")
    assert response.status_code == 404
