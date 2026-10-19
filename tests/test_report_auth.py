"""Auth/ownership tests for the report module.

Regression guard for the P0 finding: report endpoints accepted an arbitrary
``session_id``/``report_id`` and returned another session's data (cross-session
read through report generation and through report retrieval), and the export
endpoints were fully unauthenticated.

These tests exercise only isolated, synthetic session identifiers.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.auth import create_session_token
from server.main import app


def _bearer(session_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_session_token(session_id)}"}


@pytest.mark.asyncio
async def test_report_generate_without_token_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/report/generate", json={"session_id": "report-owner-401"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_generate_cannot_read_another_session():
    """A caller with a valid token must not generate a report for someone else's session."""
    attacker = "report-attacker-cross"
    victim = "report-victim-cross"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/report/generate",
            json={"session_id": victim},
            headers=_bearer(attacker),
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_retrieval_requires_owner_token():
    owner = "report-owner-read"
    attacker = "report-attacker-read"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen = await client.post(
            "/api/v1/report/generate",
            json={"session_id": owner, "student_name": "隔离考生"},
            headers=_bearer(owner),
        )
        assert gen.status_code == 200
        report_id = gen.json()["report_id"]

        # No token at all
        assert (await client.get(f"/api/v1/report/{report_id}")).status_code == 401
        assert (await client.get(f"/api/v1/report/{report_id}/html")).status_code == 401
        assert (await client.get(f"/api/v1/report/{report_id}/cover.svg")).status_code == 401

        # Another session's token
        assert (await client.get(f"/api/v1/report/{report_id}", headers=_bearer(attacker))).status_code == 401
        assert (await client.get(f"/api/v1/report/{report_id}/html", headers=_bearer(attacker))).status_code == 401
        assert (await client.get(f"/api/v1/report/{report_id}/cover.svg", headers=_bearer(attacker))).status_code == 401

        # The owner can read all three representations
        assert (await client.get(f"/api/v1/report/{report_id}", headers=_bearer(owner))).status_code == 200
        assert (await client.get(f"/api/v1/report/{report_id}/html", headers=_bearer(owner))).status_code == 200
        assert (await client.get(f"/api/v1/report/{report_id}/cover.svg", headers=_bearer(owner))).status_code == 200


@pytest.mark.asyncio
async def test_report_retrieval_with_invalid_token_is_rejected():
    owner = "report-owner-bad-token"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen = await client.post("/api/v1/report/generate", json={"session_id": owner}, headers=_bearer(owner))
        report_id = gen.json()["report_id"]
        response = await client.get(
            f"/api/v1/report/{report_id}",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_malicious_report_id_is_rejected_cleanly():
    """A path-traversal style report id must be rejected without touching the FS."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/report/..%2F..%2Fetc%2Fpasswd", headers=_bearer("report-any-session"))
    assert response.status_code in (400, 404)
