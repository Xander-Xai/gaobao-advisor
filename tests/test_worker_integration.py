"""Real MySQL + Redis multi-worker and recovery integration tests.

Run with both services available::

    MYSQL_TEST_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_test?charset=utf8mb4' \\
    REDIS_TEST_URL='redis://127.0.0.1:6380/0' \\
      python -m pytest tests/test_worker_integration.py -q

The database name must contain ``test``; the fixture drops/recreates only that
schema.
"""

from __future__ import annotations

import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import DataQualityJob, OperationAuditLog, QualityTaskOutbox
from server.admin import repository
from server.admin.queue import RedisQueue, dispatch_outbox
from server.admin.worker import run_once
from tests.conftest import _seed

MYSQL_URL = os.getenv("MYSQL_TEST_URL", "").strip()
REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "").strip()
pytestmark = [
    pytest.mark.mysql,
    pytest.mark.redis,
    pytest.mark.skipif(
        not MYSQL_URL or not REDIS_TEST_URL,
        reason="MYSQL_TEST_URL and REDIS_TEST_URL are required",
    ),
]


def _database_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


@pytest.fixture
def mysql_factory():
    if "test" not in _database_name(MYSQL_URL):
        pytest.skip("MYSQL_TEST_URL database name must contain 'test'")
    engine = create_engine(MYSQL_URL, pool_pre_ping=True, pool_recycle=1800)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        _seed(session)
    finally:
        session.close()
    yield factory
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def redis_queue():
    queue = RedisQueue(url=REDIS_TEST_URL, key=f"gaobao:test:worker:{uuid.uuid4().hex}")
    if not queue.ping():
        pytest.skip("Redis is not reachable")
    try:
        yield queue
    finally:
        try:
            queue._connect().delete(queue.key)  # noqa: SLF001 - test cleanup
        finally:
            queue.close()


def _create_job(factory, key: str, *, max_attempts: int = 3) -> int:
    session = factory()
    try:
        job, _ = repository.create_job_with_outbox(
            session,
            filters={},
            idempotency_key=key,
            actor="operator",
            role="operator",
            request_id=f"req-{key}",
            ip_hash=None,
            max_attempts=max_attempts,
        )
        return job.id
    finally:
        session.close()


def _age_started(factory, job_id: int, seconds: int = 120) -> None:
    session = factory()
    try:
        job = session.get(DataQualityJob, job_id)
        job.started_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
            seconds=seconds
        )
        session.commit()
    finally:
        session.close()


def test_two_workers_race_for_one_redis_message(mysql_factory, redis_queue, monkeypatch):
    job_id = _create_job(mysql_factory, "mw-race-000001")
    monkeypatch.setattr("db.database.SessionLocal", mysql_factory)
    assert dispatch_outbox(job_id=job_id, queue=redis_queue) == {"published": 1, "failed": 0, "skipped": 0}

    def work(_index: int):
        session = mysql_factory()
        try:
            return run_once(queue=redis_queue, db=session, timeout=1)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, range(2)))

    statuses = sorted(result["status"] for result in results)
    assert statuses == ["IDLE", "SUCCEEDED"], results

    session = mysql_factory()
    try:
        job = session.get(DataQualityJob, job_id)
        assert job.status == "SUCCEEDED"
        assert session.query(OperationAuditLog).filter_by(action="quality_job.started").count() == 1
        assert session.query(OperationAuditLog).filter_by(action="quality_job.succeeded").count() == 1
    finally:
        session.close()


def test_fenced_old_worker_cannot_complete_after_reclaim(mysql_factory):
    session = mysql_factory()
    try:
        job, _ = repository.create_job_with_outbox(
            session,
            filters={},
            idempotency_key="mw-fencing-0001",
            actor="operator",
            role="operator",
            request_id="req-mw-fencing",
            ip_hash=None,
        )
        job_id = job.id
        assert repository.claim_job(session, job_id) == 1
    finally:
        session.close()
    _age_started(mysql_factory, job_id)

    session = mysql_factory()
    try:
        assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
        assert repository.claim_job(session, job_id) == 2
        with pytest.raises(Exception) as error:
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
        assert getattr(error.value, "code", None) == "EXECUTION_FENCED"
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


def test_mysql_lease_exhaustion_marks_failed(mysql_factory):
    job_id = _create_job(mysql_factory, "mw-exhaust-0001", max_attempts=1)
    session = mysql_factory()
    try:
        assert repository.claim_job(session, job_id) == 1
    finally:
        session.close()
    _age_started(mysql_factory, job_id)
    session = mysql_factory()
    try:
        assert repository.requeue_stale_running(session, older_than_seconds=60) == 1
        job = session.get(DataQualityJob, job_id)
        assert job.status == "FAILED"
        assert job.error_code == "WORKER_LEASE_EXPIRED"
        assert session.query(OperationAuditLog).filter_by(action="quality_job.failed").count() == 1
    finally:
        session.close()


def test_duplicate_delivery_does_not_duplicate_issues(mysql_factory, redis_queue, monkeypatch):
    job_id = _create_job(mysql_factory, "mw-duplicate-0001")
    monkeypatch.setattr("db.database.SessionLocal", mysql_factory)
    assert dispatch_outbox(job_id=job_id, queue=redis_queue) == {"published": 1, "failed": 0, "skipped": 0}
    redis_queue.enqueue(job_id)  # duplicate message

    session = mysql_factory()
    try:
        first = run_once(queue=redis_queue, db=session, timeout=1)
        second = run_once(queue=redis_queue, db=session, timeout=1)
        job = session.get(DataQualityJob, job_id)
        assert first["status"] == "SUCCEEDED"
        assert second["status"] == "SUCCEEDED"
        assert job.issue_count == first["issue_count"]
        assert session.query(OperationAuditLog).filter_by(action="quality_job.succeeded").count() == 1
    finally:
        session.close()


def test_two_workers_recover_one_stale_lease(mysql_factory):
    job_id = _create_job(mysql_factory, "mw-recovery-0001")
    session = mysql_factory()
    try:
        assert repository.claim_job(session, job_id) == 1
    finally:
        session.close()
    _age_started(mysql_factory, job_id)

    def recover(_index: int) -> int:
        session = mysql_factory()
        try:
            return repository.requeue_stale_running(session, older_than_seconds=60)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(recover, range(2)))
    assert results == [0, 1], results

    session = mysql_factory()
    try:
        job = session.get(DataQualityJob, job_id)
        outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
        assert job.status == "PENDING"
        assert outbox.status == "PENDING"
        assert session.query(OperationAuditLog).filter_by(action="quality_job.retry_scheduled").count() == 1
    finally:
        session.close()
