"""Quality-job workflow: idempotency, async queue semantics, review and audit."""

from __future__ import annotations

import uuid

import pytest

from db.models import DataQualityIssue, DataQualityJob, OperationAuditLog, QualityTaskOutbox
from server.admin import repository, service, worker
from server.admin.queue import QueueUnavailable, dispatch_outbox
from server.admin.worker import RetryableJobError, execute_job, run_once
from tests.conftest import auth_header, login


class FakeQueue:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.items: list[int] = []

    def ping(self) -> bool:
        return not self.fail

    def enqueue(self, job_id: int) -> None:
        if self.fail:
            raise QueueUnavailable("fake redis down")
        self.items.append(job_id)

    def dequeue(self, timeout: int = 2) -> int | None:
        if self.fail:
            raise QueueUnavailable("fake redis down")
        return self.items.pop(0) if self.items else None

    def depth(self) -> int:
        return len(self.items)


def _create(client, token, key: str, filters: dict | None = None):
    return client.post(
        "/api/v1/admin/quality/jobs",
        json={"filters": filters or {}},
        headers={**auth_header(token), "Idempotency-Key": key},
    )


class TestInlineWorkflow:
    def test_operator_creates_job_and_gets_real_findings(self, admin_client):
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "inline-job-key-0001", {"province": "示例省·甲"})
        assert response.status_code == 201, response.text
        body = response.json()
        job = body["job"]
        assert job["status"] == "SUCCEEDED"
        assert job["execution_mode"] == "inline_degraded"
        assert job["issue_count"] > 0
        assert job["checked_rows"] > 0
        assert body["queue_state"] == "INLINE"
        assert body["warning"]

        detail = admin_client.get(
            f"/api/v1/admin/quality/jobs/{job['id']}",
            headers=auth_header(token),
        )
        assert detail.status_code == 200
        codes = {issue["rule_code"] for issue in detail.json()["issues"]}
        assert "score_out_of_range" in codes
        assert "score_order_invalid" in codes
        assert "plan_count_invalid" in codes

    def test_same_idempotency_key_replays_same_job(self, admin_client):
        token = login(admin_client, "operator")
        first = _create(admin_client, token, "replay-key-000001", {})
        assert first.status_code == 201
        second = _create(admin_client, token, "replay-key-000001", {})
        assert second.status_code == 200
        assert second.json()["replayed"] is True
        assert second.json()["job"]["id"] == first.json()["job"]["id"]

    def test_same_key_with_different_filters_conflicts(self, admin_client):
        token = login(admin_client, "operator")
        assert _create(admin_client, token, "conflict-key-00001", {"province": "示例省·甲"}).status_code == 201
        response = _create(admin_client, token, "conflict-key-00001", {"province": "示例省·乙"})
        assert response.status_code == 409
        assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"

    def test_unknown_school_scope_succeeds_with_info_issue(self, admin_client):
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "empty-scope-key-01", {"school_id": 999999})
        assert response.status_code == 201
        job = response.json()["job"]
        assert job["status"] == "SUCCEEDED"
        detail = admin_client.get(
            f"/api/v1/admin/quality/jobs/{job['id']}",
            headers=auth_header(token),
        )
        assert detail.json()["issues"][0]["rule_code"] == "no_schools_matched"

    def test_extra_filter_field_is_rejected(self, admin_client):
        token = login(admin_client, "operator")
        response = admin_client.post(
            "/api/v1/admin/quality/jobs",
            json={"filters": {"sql": "drop table schools"}},
            headers={**auth_header(token), "Idempotency-Key": "invalid-filter-key"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


class TestQueueSemantics:
    def test_async_mode_without_redis_does_not_fake_success(self, admin_client, monkeypatch, admin_factory):
        monkeypatch.setenv("QUALITY_TASK_MODE", "async")
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "async-no-redis-key", {})
        assert response.status_code == 202
        body = response.json()
        assert body["job"]["status"] == "PENDING"
        assert body["queue_state"] == "UNAVAILABLE"
        assert body["warning"]
        assert body["job"]["execution_mode"] == "pending"

        session = admin_factory()
        try:
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=body["job"]["id"]).one()
            assert outbox.status == "PENDING"
        finally:
            session.close()

    def test_async_mode_dispatches_to_queue(self, admin_client, monkeypatch, admin_factory):
        monkeypatch.setenv("QUALITY_TASK_MODE", "async")
        fake = FakeQueue()
        monkeypatch.setattr(service, "get_queue", lambda: fake)
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "async-queue-key-01", {})
        assert response.status_code == 202
        body = response.json()
        assert body["queue_state"] == "DISPATCHED"
        assert fake.items == [body["job"]["id"]]

        session = admin_factory()
        try:
            result = execute_job(body["job"]["id"], session=session)
        finally:
            session.close()
        assert result["status"] == "SUCCEEDED"
        assert result["issue_count"] > 0

    def test_queue_failure_keeps_job_pending(self, admin_client, monkeypatch):
        monkeypatch.setenv("QUALITY_TASK_MODE", "async")
        monkeypatch.setattr(service, "get_queue", lambda: FakeQueue(fail=True))
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "async-down-key-001", {})
        assert response.status_code == 202
        body = response.json()
        assert body["queue_state"] == "UNAVAILABLE"
        assert body["job"]["status"] == "PENDING"

    def test_disabled_mode_returns_503_and_creates_nothing(self, admin_client, monkeypatch, admin_factory):
        monkeypatch.setenv("QUALITY_TASK_MODE", "disabled")
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "disabled-key-00001", {})
        assert response.status_code == 503
        assert response.json()["code"] == "FEATURE_DISABLED"
        session = admin_factory()
        try:
            assert session.query(DataQualityJob).count() == 0
        finally:
            session.close()


class TestWorker:
    def _pending_job(self, client, monkeypatch) -> tuple[int, object]:
        monkeypatch.setenv("QUALITY_TASK_MODE", "async")
        fake = FakeQueue()
        monkeypatch.setattr(service, "get_queue", lambda: fake)
        token = login(client, "operator")
        response = _create(client, token, f"worker-key-{uuid.uuid4().hex[:12]}", {})
        assert response.status_code == 202
        return response.json()["job"]["id"], fake

    def test_worker_success_and_duplicate_claim(self, admin_client, monkeypatch, admin_factory):
        job_id, _ = self._pending_job(admin_client, monkeypatch)
        session = admin_factory()
        try:
            first = execute_job(job_id, session=session)
            second = execute_job(job_id, session=session)
            issues = session.query(DataQualityIssue).filter_by(job_id=job_id).count()
        finally:
            session.close()
        assert first["status"] == "SUCCEEDED"
        assert second["status"] == "SUCCEEDED"
        assert issues == first["issue_count"]

    def test_transient_failures_retry_then_fail(self, admin_client, monkeypatch, admin_factory):
        job_id, _ = self._pending_job(admin_client, monkeypatch)

        def boom(session, filters):
            raise RetryableJobError("temporary database hiccup")

        monkeypatch.setattr(worker, "collect_issues", boom)
        for attempt in (1, 2):
            session = admin_factory()
            try:
                result = execute_job(job_id, session=session)
            finally:
                session.close()
            assert result["status"] == "PENDING"
            assert result["attempts"] == attempt
        session = admin_factory()
        try:
            result = execute_job(job_id, session=session)
            job = session.get(DataQualityJob, job_id)
        finally:
            session.close()
        assert result["status"] == "FAILED"
        assert result["attempts"] == 3
        assert job.error_code == "QUALITY_JOB_TRANSIENT"

    def test_permanent_failure_marks_failed(self, admin_client, monkeypatch, admin_factory):
        job_id, _ = self._pending_job(admin_client, monkeypatch)

        def boom(session, filters):
            raise ValueError("bad rule implementation")

        monkeypatch.setattr(worker, "collect_issues", boom)
        session = admin_factory()
        try:
            result = execute_job(job_id, session=session)
            job = session.get(DataQualityJob, job_id)
        finally:
            session.close()
        assert result["status"] == "FAILED"
        assert job.error_code == "QUALITY_JOB_FAILED"
        assert job.finished_at is not None

    def test_stale_running_job_is_requeued(self, admin_factory):
        import datetime

        session = admin_factory()
        try:
            job = DataQualityJob(
                idempotency_key="stale-key-000001",
                requested_by="operator",
                status="RUNNING",
                attempts=1,
                started_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            )
            session.add(job)
            session.commit()
            count = repository.requeue_stale_running(session, older_than_seconds=60)
            session.refresh(job)
            assert count == 1
            assert job.status == "PENDING"
            assert job.error_code == "WORKER_LEASE_EXPIRED"
        finally:
            session.close()


class TestReviewAndAudit:
    def test_admin_reviews_with_optimistic_version(self, admin_client):
        operator = login(admin_client, "operator")
        created = _create(admin_client, operator, "review-key-000001", {}).json()["job"]
        assert created["review_status"] == "PENDING_REVIEW"

        admin = login(admin_client, "admin")
        response = admin_client.post(
            f"/api/v1/admin/quality/jobs/{created['id']}/review",
            json={"decision": "APPROVED", "note": "已复核合成数据", "expected_version": created["version"]},
            headers=auth_header(admin),
        )
        assert response.status_code == 200
        reviewed = response.json()
        assert reviewed["review_status"] == "APPROVED"
        assert reviewed["reviewed_by"] == "admin"
        assert reviewed["version"] == created["version"] + 1

        again = admin_client.post(
            f"/api/v1/admin/quality/jobs/{created['id']}/review",
            json={"decision": "REJECTED", "note": "", "expected_version": reviewed["version"]},
            headers=auth_header(admin),
        )
        assert again.status_code == 409
        assert again.json()["code"] == "ALREADY_REVIEWED"

        logs = admin_client.get("/api/v1/admin/audit-logs", headers=auth_header(admin)).json()
        actions = {item["action"] for item in logs["items"]}
        assert {"quality_job.created", "quality_job.succeeded", "quality_job.reviewed"} <= actions
        reviewed_log = next(item for item in logs["items"] if item["action"] == "quality_job.reviewed")
        assert reviewed_log["actor"] == "admin"
        assert reviewed_log["resource_id"] == str(created["id"])

    def test_stale_version_conflicts(self, admin_client):
        operator = login(admin_client, "operator")
        created = _create(admin_client, operator, "version-key-00001", {}).json()["job"]
        admin = login(admin_client, "admin")
        response = admin_client.post(
            f"/api/v1/admin/quality/jobs/{created['id']}/review",
            json={"decision": "APPROVED", "note": "", "expected_version": created["version"] - 1},
            headers=auth_header(admin),
        )
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "VERSION_CONFLICT"
        assert body["details"]["current_version"] == created["version"]

    def test_missing_job_returns_404(self, admin_client):
        token = login(admin_client, "admin")
        response = admin_client.get("/api/v1/admin/quality/jobs/999999", headers=auth_header(token))
        assert response.status_code == 404
        assert response.json()["code"] == "JOB_NOT_FOUND"

    def test_unexpected_error_rolls_back_and_returns_envelope(self, admin_client, admin_factory, monkeypatch):
        def explode(*args, **kwargs):
            raise RuntimeError("audit backend exploded")

        monkeypatch.setattr(repository, "record_audit", explode)
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "rollback-key-0001", {})
        assert response.status_code == 500
        assert response.json()["code"] == "INTERNAL_ERROR"
        session = admin_factory()
        try:
            assert session.query(DataQualityJob).count() == 0
            assert session.query(QualityTaskOutbox).count() == 0
            assert session.query(OperationAuditLog).count() == 0
        finally:
            session.close()


class TestOutboxDispatch:
    def test_dispatch_publishes_pending_outbox_and_marks_it(self, admin_factory, monkeypatch):
        session = admin_factory()
        try:
            job, _ = repository.create_job_with_outbox(
                session,
                filters={},
                idempotency_key="outbox-key-000001",
                actor="operator",
                role="operator",
                request_id="req-outbox",
                ip_hash=None,
            )
            job_id = job.id
        finally:
            session.close()
        monkeypatch.setattr("db.database.SessionLocal", admin_factory)
        fake = FakeQueue()
        result = dispatch_outbox(job_id=job_id, queue=fake)
        assert result == {"published": 1, "failed": 0, "skipped": 0}
        assert fake.items == [job_id]
        session = admin_factory()
        try:
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
            assert outbox.status == "DISPATCHED"
        finally:
            session.close()

    def test_dispatch_failure_keeps_outbox_pending(self, admin_factory, monkeypatch):
        session = admin_factory()
        try:
            job, _ = repository.create_job_with_outbox(
                session,
                filters={},
                idempotency_key="outbox-key-000002",
                actor="operator",
                role="operator",
                request_id="req-outbox",
                ip_hash=None,
            )
            job_id = job.id
        finally:
            session.close()
        monkeypatch.setattr("db.database.SessionLocal", admin_factory)
        result = dispatch_outbox(job_id=job_id, queue=FakeQueue(fail=True))
        assert result == {"published": 0, "failed": 1, "skipped": 0}
        session = admin_factory()
        try:
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
            assert outbox.status == "PENDING"
            assert outbox.attempts == 1
            assert "fake redis down" in (outbox.last_error or "")
        finally:
            session.close()

    def test_run_once_without_redis_raises(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        with pytest.raises(QueueUnavailable):
            run_once()
