"""Quality-job workflow: idempotency, async queue semantics, review and audit."""

from __future__ import annotations

import datetime
import types
import uuid

import pytest

from db.models import DataQualityIssue, DataQualityJob, OperationAuditLog, QualityTaskOutbox
from server.admin import repository, service, worker
from server.admin.errors import AdminError
from server.admin.queue import QueueUnavailable, dispatch_outbox
from server.admin.worker import RetryableJobError, execute_job, recover_worker_state, run_once
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

    def test_inline_retry_does_not_mark_outbox_dispatched(self, admin_client, monkeypatch, admin_factory):
        """A retryable inline failure must leave the outbox armed for a worker.

        Regression: the inline path used to mark the outbox DISPATCHED even
        though the job had gone back to PENDING, stranding it forever when no
        Redis queue existed.
        """

        def boom(session, filters):
            raise RetryableJobError("temporary inline failure")

        monkeypatch.setattr(worker, "collect_issues", boom)
        token = login(admin_client, "operator")
        response = _create(admin_client, token, "inline-retry-key-01", {})
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["job"]["status"] == "PENDING"
        assert body["job"]["attempts"] == 1
        assert body["job"]["execution_mode"] == "inline_degraded"
        assert body["queue_state"] == "INLINE"
        assert "重试" in (body["warning"] or "")

        session = admin_factory()
        try:
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=body["job"]["id"]).one()
            assert outbox.status == "PENDING"
            assert outbox.next_attempt_at is not None
        finally:
            session.close()

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


class TestFencingAndLeaseRecovery:
    def _create(self, session, key: str, max_attempts: int = 3) -> int:
        job, _ = repository.create_job_with_outbox(
            session,
            filters={},
            idempotency_key=key,
            actor="operator",
            role="operator",
            request_id="req-fencing",
            ip_hash=None,
            max_attempts=max_attempts,
        )
        return job.id

    def _age_started(self, session, job_id: int, seconds: int = 120) -> None:
        job = session.get(DataQualityJob, job_id)
        job.started_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
            seconds=seconds
        )
        session.commit()

    def test_claim_returns_fencing_attempt_and_stale_complete_is_rejected(self, admin_factory):
        session = admin_factory()
        try:
            job_id = self._create(session, "fencing-complete-001")
            assert repository.claim_job(session, job_id) == 1
            assert repository.claim_job(session, job_id) is None
            self._age_started(session, job_id)
            assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
            assert repository.claim_job(session, job_id) == 2

            with pytest.raises(AdminError) as error:
                repository.complete_job(
                    session,
                    job_id,
                    checked_rows=1,
                    issues=[],
                    request_id="req-old",
                    actor="worker-old",
                    role="system",
                    expected_attempt=1,
                )
            assert error.value.code == "EXECUTION_FENCED"

            finished = repository.complete_job(
                session,
                job_id,
                checked_rows=1,
                issues=[],
                request_id="req-new",
                actor="worker-new",
                role="system",
                expected_attempt=2,
            )
            assert finished.status == "SUCCEEDED"
            assert session.query(OperationAuditLog).filter_by(action="quality_job.succeeded").count() == 1
        finally:
            session.close()

    def test_stale_failure_cannot_overwrite_new_execution(self, admin_factory):
        session = admin_factory()
        try:
            job_id = self._create(session, "fencing-fail-00001")
            assert repository.claim_job(session, job_id) == 1
            self._age_started(session, job_id)
            assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
            assert repository.claim_job(session, job_id) == 2

            with pytest.raises(AdminError) as error:
                repository.fail_job(
                    session,
                    job_id,
                    error_code="QUALITY_JOB_FAILED",
                    error_message="old worker",
                    retryable=False,
                    request_id="req-old",
                    actor="worker-old",
                    role="system",
                    expected_attempt=1,
                )
            assert error.value.code == "EXECUTION_FENCED"
            assert session.get(DataQualityJob, job_id).status == "RUNNING"

            failed = repository.fail_job(
                session,
                job_id,
                error_code="QUALITY_JOB_FAILED",
                error_message="new worker",
                retryable=False,
                request_id="req-new",
                actor="worker-new",
                role="system",
                expected_attempt=2,
            )
            assert failed.status == "FAILED"
        finally:
            session.close()

    @pytest.mark.parametrize("max_attempts", [1, 3])
    def test_lease_exhaustion_marks_failed(self, admin_factory, max_attempts):
        session = admin_factory()
        try:
            job_id = self._create(session, f"lease-exhaust-{max_attempts}", max_attempts=max_attempts)
            for attempt in range(1, max_attempts + 1):
                assert repository.claim_job(session, job_id) == attempt
                self._age_started(session, job_id)
                assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
                job = session.get(DataQualityJob, job_id)
                if attempt < max_attempts:
                    assert job.status == "PENDING"
                else:
                    assert job.status == "FAILED"
                    assert job.error_code == "WORKER_LEASE_EXPIRED"
                    assert job.finished_at is not None
            assert session.query(OperationAuditLog).filter_by(action="quality_job.failed").count() == 1
        finally:
            session.close()

    def test_repeated_recovery_is_idempotent(self, admin_factory):
        session = admin_factory()
        try:
            job_id = self._create(session, "lease-idempotent-01")
            assert repository.claim_job(session, job_id) == 1
            self._age_started(session, job_id)
            assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
            version = session.get(DataQualityJob, job_id).version
            assert repository.requeue_stale_running(session, older_than_seconds=60) == 0
            assert session.get(DataQualityJob, job_id).version == version
        finally:
            session.close()

    def test_recover_worker_state_runs_both_bounded_scans(self, admin_factory, monkeypatch):
        session = admin_factory()
        try:
            stale_id = self._create(session, "recover-state-stale-01")
            assert repository.claim_job(session, stale_id) == 1
            self._age_started(session, stale_id)

            orphan_id = self._create(session, "recover-state-orphan-01")
            repository.mark_outbox_dispatched(session, orphan_id)
            orphan = session.get(DataQualityJob, orphan_id)
            orphan.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
                seconds=120
            )
            session.commit()
        finally:
            session.close()

        monkeypatch.setattr(worker, "SessionLocal", admin_factory)
        counts = recover_worker_state(stale_running_seconds=60, orphaned_seconds=60)
        assert counts == {"stale_running": 1, "orphaned_dispatched": 1}
        session = admin_factory()
        try:
            assert session.get(DataQualityJob, stale_id).status == "PENDING"
            assert session.get(DataQualityJob, orphan_id).status == "PENDING"
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=orphan_id).one()
            assert outbox.status == "PENDING"
        finally:
            session.close()

    def test_claim_db_failure_does_not_persist_false_failure(self, admin_factory, monkeypatch):
        session = admin_factory()
        try:
            job_id = self._create(session, "claim-db-failure-01")

            def broken_claim(*args, **kwargs):
                raise RuntimeError("database unavailable during claim")

            monkeypatch.setattr(repository, "claim_job", broken_claim)
            with pytest.raises(RuntimeError, match="database unavailable"):
                execute_job(job_id, session=session)
            session.expire_all()
            job = session.get(DataQualityJob, job_id)
            assert job.status == "PENDING"
            assert session.query(OperationAuditLog).filter_by(action="quality_job.failed").count() == 0
        finally:
            session.close()

    def test_worker_loop_runs_periodic_recovery_before_consuming(self, monkeypatch):
        calls = []
        stop = {"flag": False}

        def fake_recover(**kwargs):
            calls.append(kwargs)
            return {"stale_running": 0, "orphaned_dispatched": 0}

        def fake_run_once(**kwargs):
            stop["flag"] = True
            return {"job_id": None, "status": "IDLE"}

        monkeypatch.setattr(worker, "recover_worker_state", fake_recover)
        monkeypatch.setattr(worker, "run_once", fake_run_once)
        worker._worker_loop(
            queue=object(),
            timeout=0,
            stop=stop,
            stale_lease=600,
            delivery_lease=60,
            recovery_interval=0,
        )
        assert calls == [{"stale_running_seconds": 600, "orphaned_seconds": 60}]

    def test_run_forever_runs_startup_recovery(self, monkeypatch):
        recovery_calls = []
        loop_calls = []
        queue = types.SimpleNamespace(url="redis://example/0", key="queue")

        monkeypatch.setattr(worker, "get_queue", lambda: queue)
        monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
        monkeypatch.setattr(
            worker,
            "recover_worker_state",
            lambda **kwargs: recovery_calls.append(kwargs) or {"stale_running": 0, "orphaned_dispatched": 0},
        )
        monkeypatch.setattr(worker, "_worker_loop", lambda **kwargs: loop_calls.append(kwargs))
        worker.run_forever()
        assert recovery_calls
        assert loop_calls

    def test_recover_worker_state_surfaces_db_failure(self, monkeypatch):
        def broken_session():
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(worker, "SessionLocal", broken_session)
        with pytest.raises(RuntimeError, match="database unavailable"):
            recover_worker_state()


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


class TestDeliveryCrashWindow:
    """BRPOP removes the message before claim_job; recover that lost-delivery state."""

    def _create_dispatched_but_unclaimed(self, session, key: str) -> int:
        job, _ = repository.create_job_with_outbox(
            session,
            filters={},
            idempotency_key=key,
            actor="operator",
            role="operator",
            request_id="req-crash-window",
            ip_hash=None,
        )
        job_id = job.id
        repository.mark_outbox_dispatched(session, job_id)
        job = session.get(DataQualityJob, job_id)
        job.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
            seconds=120
        )
        session.commit()
        return job_id

    def test_orphaned_pending_dispatched_job_is_rearmed(self, admin_factory):
        session = admin_factory()
        try:
            job_id = self._create_dispatched_but_unclaimed(session, "crash-window-key-001")
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
            assert outbox.status == "DISPATCHED"

            assert repository.requeue_orphaned_dispatched(session, older_than_seconds=60) == 1
            session.refresh(outbox)
            job = session.get(DataQualityJob, job_id)
            assert job.status == "PENDING"
            assert outbox.status == "PENDING"
            assert outbox.attempts == 1
            assert outbox.dispatched_at is None
            assert "delivery lease" in (outbox.last_error or "")

            # A recent dispatch is not re-armed, so the normal in-flight window
            # is not disturbed.
            repository.mark_outbox_dispatched(session, job_id)
            assert repository.requeue_orphaned_dispatched(session, older_than_seconds=60) == 0
        finally:
            session.close()

    def test_recovered_job_is_redelivered_and_processed(self, admin_factory, monkeypatch):
        session = admin_factory()
        try:
            job_id = self._create_dispatched_but_unclaimed(session, "crash-window-key-002")
            assert repository.requeue_orphaned_dispatched(session, older_than_seconds=60) == 1

            monkeypatch.setattr("db.database.SessionLocal", admin_factory)
            fake = FakeQueue()
            result = run_once(queue=fake, db=session)
            assert result["job_id"] == job_id
            assert result["status"] == "SUCCEEDED"
            job = session.get(DataQualityJob, job_id)
            outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
            assert job.status == "SUCCEEDED"
            assert outbox.status == "DISPATCHED"
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
