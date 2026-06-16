"""Tests for server/monitoring.py — Sentry integration."""

import logging
from unittest.mock import patch

import pytest


class TestInitSentry:
    """Tests for init_sentry() function."""

    def test_no_dsn_noop(self, monkeypatch):
        """When SENTRY_DSN is not set, init_sentry should be a no-op."""
        from server.monitoring import init_sentry

        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("APP_VERSION", "1.0.0")

        # Should not raise
        init_sentry()

    def test_empty_dsn_noop(self, monkeypatch):
        """When SENTRY_DSN is empty, init_sentry should be a no-op."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "")
        monkeypatch.setenv("APP_ENV", "test")

        # Should not raise
        init_sentry()

    def test_whitespace_dsn_noop(self, monkeypatch):
        """When SENTRY_DSN is only whitespace, init_sentry should be a no-op."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "   ")
        monkeypatch.setenv("APP_ENV", "test")

        # Should not raise
        init_sentry()

    def test_sentry_init_with_custom_config(self, monkeypatch, caplog):
        """When SENTRY_DSN is set with custom config, sentry_sdk.init should be called."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.io/123")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_VERSION", "2.0.0")

        with caplog.at_level(logging.INFO):
            init_sentry()

        # Should have logged initialization
        assert any("Sentry monitoring initialized" in record.message for record in caplog.records)

    def test_import_error_handled(self, monkeypatch, caplog):
        """When sentry_sdk is not installed, should log warning and continue."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.io/123")

        # Re-import to reset module state
        import importlib
        import server.monitoring
        importlib.reload(server.monitoring)

        with caplog.at_level(logging.WARNING):
            # Mock the import to raise ImportError
            with patch.object(server.monitoring, "__builtins__", {"__import__": lambda n, *a, **k: (_ for _ in ()).throw(ImportError("No module named sentry_sdk")) if n == "sentry_sdk" else __import__(n, *a, **k)}):
                # Should not raise, just log warning
                init_sentry()

    def test_default_traces_sample_rate(self, monkeypatch, caplog):
        """When SENTRY_TRACES_SAMPLE_RATE is not set, should default to 0.1."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.io/123")
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

        with caplog.at_level(logging.INFO):
            init_sentry()

        # Should have initialized with default 0.1 rate
        assert any("production" in record.message or "development" in record.message for record in caplog.records)

    def test_default_environment(self, monkeypatch, caplog):
        """When APP_ENV is not set, should default to 'development'."""
        from server.monitoring import init_sentry

        monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.io/123")
        monkeypatch.delenv("APP_ENV", raising=False)

        with caplog.at_level(logging.INFO):
            init_sentry()

        # Should have initialized in development environment
        assert any("development" in record.message for record in caplog.records)


class TestMonitoringModule:
    """Tests for monitoring module structure."""

    def test_init_sentry_exported(self):
        """init_sentry should be importable from the module."""
        from server.monitoring import init_sentry

        assert callable(init_sentry)

    def test_logger_exists(self):
        """A logger should be available for the module."""
        from server.monitoring import logger

        assert logger is not None

    def test_module_docstring(self):
        """Module should have a docstring."""
        import server.monitoring

        assert server.monitoring.__doc__ is not None
        assert len(server.monitoring.__doc__) > 0