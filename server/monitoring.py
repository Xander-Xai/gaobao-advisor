"""Application monitoring — Sentry integration for error tracking.

Usage:
    from server.monitoring import init_sentry
    init_sentry()  # call at startup
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN environment variable is set.

    Integrates with FastAPI and SQLAlchemy automatically.
    Safe to call even when SENTRY_DSN is not configured — no-op in that case.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("SENTRY_DSN not set — Sentry monitoring disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("APP_ENV", "development"),
            release=os.getenv("APP_VERSION", "unknown"),
        )
        logger.info("Sentry monitoring initialized (env=%s)", os.getenv("APP_ENV", "development"))
    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry monitoring unavailable")
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", e)
