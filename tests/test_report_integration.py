"""End-to-end report generation test."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import ASGITransport, AsyncClient

from server.auth import create_session_token
from server.main import app

SESSION_ID = "integration-test-session"


def _token():
    return create_session_token(SESSION_ID)


@pytest.mark.asyncio
async def test_full_report_pipeline():
    """Test the full report pipeline:
    1. Generate report
    2. Get report data
    3. Get report HTML
    4. Get report cover SVG
    """
    token = _token()

    # 1. Generate report
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gen_resp = await client.post(
            "/api/v1/report/generate",
            json={"session_id": SESSION_ID, "student_name": "测试考生", "token": token},
        )
        assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.status_code} {gen_resp.text}"
        data = gen_resp.json()
        assert "report_id" in data
        report_id = data["report_id"]

        # 2. Get report
        get_resp = await client.get(f"/api/v1/report/{report_id}", params={"session_id": SESSION_ID, "token": token})
        assert get_resp.status_code == 200
        report_data = get_resp.json()
        assert report_data["student_name"] == "测试考生"

        # 3. Get HTML
        html_resp = await client.get(
            f"/api/v1/report/{report_id}/html", params={"session_id": SESSION_ID, "token": token}
        )
        assert html_resp.status_code == 200
        assert "text/html" in html_resp.headers["content-type"]
        assert "金榜题名" in html_resp.text

        # 4. Get SVG cover
        svg_resp = await client.get(
            f"/api/v1/report/{report_id}/cover.svg", params={"session_id": SESSION_ID, "token": token}
        )
        assert svg_resp.status_code == 200
        assert "image/svg+xml" in svg_resp.headers["content-type"]
        assert "金榜题名" in svg_resp.text
