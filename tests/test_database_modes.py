"""Database URL validation, dialect separation and MySQL DDL compilation."""

from __future__ import annotations

import pytest
from sqlalchemy import create_mock_engine

from db import database
from db.database import Base, _normalize_url, redact_database_url
from db.models import (  # noqa: F401 - register metadata
    DataQualityIssue,
    DataQualityJob,
    OperationAuditLog,
    QualityTaskOutbox,
)


class TestUrlValidation:
    def test_mysql_scheme_is_normalized_to_pymysql(self):
        assert _normalize_url("mysql://u:p@db:3306/gaobao").startswith("mysql+pymysql://")
        assert _normalize_url("mysql+pymysql://u:p@db/gaobao").startswith("mysql+pymysql://")
        assert _normalize_url("sqlite:///data/demo.db").startswith("sqlite:///")

    def test_unsupported_scheme_fails_closed(self):
        with pytest.raises(ValueError, match="Unsupported DATABASE_URL scheme"):
            _normalize_url("postgresql://u:p@db/gaobao")

    def test_password_is_redacted(self):
        redacted = redact_database_url("mysql+pymysql://gaobao:supersecret@mysql:3306/gaobao?charset=utf8mb4")
        assert "supersecret" not in redacted
        assert "gaobao:***@mysql:3306" in redacted

    def test_sqlite_path_is_derived_from_url(self):
        assert database._sqlite_path_from_url("sqlite:////tmp/x.db") == "/tmp/x.db"  # noqa: SLF001
        assert database._sqlite_path_from_url("sqlite:///data/x.db").endswith("data/x.db")  # noqa: SLF001
        assert database._sqlite_path_from_url("mysql+pymysql://u:p@h/db") is None  # noqa: SLF001


class TestSqlitePragmaIsolation:
    def test_sqlite_engine_has_wal_listener(self):
        engine = database._create_engine("sqlite:////tmp/gaobao-mode-test.db")  # noqa: SLF001
        try:
            assert engine.dialect.name == "sqlite"
            assert engine.pool is not None
        finally:
            engine.dispose()

    def test_mysql_engine_does_not_attach_sqlite_listener(self, monkeypatch):
        """Construct a MySQL engine without connecting (no server required)."""
        captured = {}

        def fake_create_engine(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(database, "create_engine", fake_create_engine)
        database._create_engine("mysql+pymysql://u:p@127.0.0.1:3306/gaobao")  # noqa: SLF001
        assert captured["url"].startswith("mysql+pymysql://")
        assert "check_same_thread" not in captured["kwargs"].get("connect_args", {})
        assert captured["kwargs"]["pool_pre_ping"] is True
        assert captured["kwargs"]["connect_args"]["charset"] == "utf8mb4"


def test_admin_tables_compile_for_mysql_dialect():
    statements: list[str] = []
    engine = create_mock_engine(
        "mysql+pymysql://",
        lambda sql, *args, **kwargs: statements.append(str(sql.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine)
    ddl = "\n".join(statements)
    for table in (
        "data_quality_jobs",
        "data_quality_issues",
        "operation_audit_logs",
        "quality_task_outbox",
    ):
        assert table in ddl
    assert "AUTO_INCREMENT" in ddl
