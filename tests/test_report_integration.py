"""End-to-end report generation test."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server.auth import create_session_token
from server.main import app

client = TestClient(app)


def test_full_report_pipeline():
    """Test the full report pipeline (owner-authenticated):
    1. Generate report
    2. Get report data
    3. Get report HTML
    4. Get report cover SVG
    """
    session_id = "integration-test-session"
    auth = {"Authorization": f"Bearer {create_session_token(session_id)}"}

    # 1. Generate report
    gen_resp = client.post(
        "/api/v1/report/generate",
        json={"session_id": session_id, "student_name": "测试考生"},
        headers=auth,
    )
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert "report_id" in data
    report_id = data["report_id"]

    # 2. Get report
    get_resp = client.get(f"/api/v1/report/{report_id}", headers=auth)
    assert get_resp.status_code == 200
    report_data = get_resp.json()
    assert report_data["student_name"] == "测试考生"

    # 3. Get HTML
    html_resp = client.get(f"/api/v1/report/{report_id}/html", headers=auth)
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "金榜题名" in html_resp.text

    # 4. Get SVG cover
    svg_resp = client.get(f"/api/v1/report/{report_id}/cover.svg", headers=auth)
    assert svg_resp.status_code == 200
    assert "image/svg+xml" in svg_resp.headers["content-type"]
    assert "金榜题名" in svg_resp.text
