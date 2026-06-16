"""End-to-end report generation test."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_full_report_pipeline():
    """Test the full report pipeline:
    1. Generate report
    2. Get report data
    3. Get report HTML
    4. Get report cover SVG
    """
    # 1. Generate report
    gen_resp = client.post("/api/v1/report/generate", json={
        "session_id": "integration-test-session",
        "student_name": "测试考生"
    })
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert "report_id" in data
    report_id = data["report_id"]

    # 2. Get report
    get_resp = client.get(f"/api/v1/report/{report_id}")
    assert get_resp.status_code == 200
    report_data = get_resp.json()
    assert report_data["student_name"] == "测试考生"

    # 3. Get HTML
    html_resp = client.get(f"/api/v1/report/{report_id}/html")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "金榜题名" in html_resp.text

    # 4. Get SVG cover
    svg_resp = client.get(f"/api/v1/report/{report_id}/cover.svg")
    assert svg_resp.status_code == 200
    assert "image/svg+xml" in svg_resp.headers["content-type"]
    assert "金榜题名" in svg_resp.text
