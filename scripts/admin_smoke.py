"""One-command admin smoke test (no server, no Redis, no model key).

    python scripts/admin_smoke.py

Creates a temporary SQLite SYNTHETIC database, configures an in-process admin,
then exercises: login -> schools -> detail -> create job -> detail -> review ->
stats -> audit. Exits non-zero on the first failed assertion.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke.db"
        password = "smoke-admin-password-2026"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["APP_ENV"] = "development"
        os.environ["QUALITY_TASK_MODE"] = "inline"
        os.environ.pop("REDIS_URL", None)

        from server.admin.auth import hash_password

        os.environ["ADMIN_USERS_JSON"] = json.dumps(
            [{"username": "smoke", "password_hash": hash_password(password, iterations=10_000), "role": "admin"}]
        )
        os.environ["ADMIN_TOKEN_SECRET"] = "smoke-token-secret-" + "x" * 48

        from scripts.seed_demo_data import seed_database

        seed_database(db_path, reset=True)

        from fastapi.testclient import TestClient

        from server.main import app

        with TestClient(app) as client:
            login = client.post("/api/v1/admin/auth/login", json={"username": "smoke", "password": password})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            schools = client.get("/api/v1/admin/schools", params={"page_size": 2}, headers=headers)
            assert schools.status_code == 200, schools.text
            assert schools.json()["total"] == 8, schools.text
            school_id = schools.json()["items"][0]["id"]

            detail = client.get(f"/api/v1/admin/schools/{school_id}", headers=headers)
            assert detail.status_code == 200 and detail.json()["scores"], detail.text

            created = client.post(
                "/api/v1/admin/quality/jobs",
                json={"filters": {}},
                headers={**headers, "Idempotency-Key": "smoke-job-key-0001"},
            )
            assert created.status_code == 201, created.text
            job = created.json()["job"]
            assert job["status"] == "SUCCEEDED" and job["execution_mode"] == "inline_degraded", job

            job_detail = client.get(f"/api/v1/admin/quality/jobs/{job['id']}", headers=headers)
            assert job_detail.status_code == 200, job_detail.text

            reviewed = client.post(
                f"/api/v1/admin/quality/jobs/{job['id']}/review",
                json={"decision": "APPROVED", "note": "smoke review", "expected_version": job["version"]},
                headers=headers,
            )
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["review_status"] == "APPROVED"

            stats = client.get("/api/v1/admin/stats", headers=headers)
            audit = client.get("/api/v1/admin/audit-logs", headers=headers)
            assert stats.status_code == 200 and stats.json()["jobs_total"] == 1, stats.text
            assert audit.status_code == 200 and audit.json()["total"] >= 4, audit.text

            print(
                json.dumps(
                    {
                        "status": "ok",
                        "schools": stats.json()["schools"],
                        "job_status": job["status"],
                        "issues": job["issue_count"],
                        "review": reviewed.json()["review_status"],
                        "audit_events": audit.json()["total"],
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
