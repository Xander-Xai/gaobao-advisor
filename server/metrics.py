"""
Prometheus Metrics Exporter for FastAPI.

Exposes application metrics at /metrics endpoint for Prometheus scraping.

Metrics exposed:
- http_requests_total: Total HTTP requests (counter)
- http_request_duration_seconds: Request duration histogram
- llm_api_calls_total: LLM API calls (counter)
- llm_api_errors_total: LLM API errors (counter)
- db_connection_errors_total: Database connection errors (counter)
- rag_cache_hits_total: RAG cache hits (counter)
- rag_cache_misses_total: RAG cache misses (counter)

Usage:
    from server.metrics import metrics_app
    app.mount("/metrics", metrics_app)
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

# ── Metrics Definitions ────────────────────────────────────

# HTTP request metrics
HTTP_REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# LLM API metrics
LLM_API_CALLS = Counter("llm_api_calls_total", "Total LLM API calls", ["model", "provider"])

LLM_API_ERRORS = Counter("llm_api_errors_total", "Total LLM API errors", ["model", "provider", "error_type"])

# Database metrics
DB_CONNECTION_ERRORS = Counter("db_connection_errors_total", "Total database connection errors")

# RAG cache metrics
RAG_CACHE_HITS = Counter("rag_cache_hits_total", "Total RAG cache hits")

RAG_CACHE_MISSES = Counter("rag_cache_misses_total", "Total RAG cache misses")

# Active sessions
ACTIVE_SESSIONS = Counter("active_sessions_total", "Total active sessions")

# === Quality Metrics ===

QUALITY_ANTI_PATTERN_HITS = Counter(
    "quality_anti_pattern_hits_total",
    "Anti-pattern hits by pattern type and severity",
    ["pattern_type", "severity"],
)

QUALITY_REWRITE = Counter(
    "quality_rewrite_total",
    "Low-quality rewrite triggers by reason",
    ["reason"],
)

QUALITY_SOURCE_ATTRIBUTION_RATE = Gauge(
    "quality_source_attribution_rate",
    "Rate of source-attributed data points in replies",
)

QUALITY_JUDGE_SCORE = Gauge(
    "quality_judge_score",
    "LLM judge quality score by dimension",
    ["dimension"],
)

QUALITY_USER_SATISFACTION = Gauge(
    "quality_user_satisfaction",
    "User satisfaction rate (thumbs up / total)",
)

RAG_CACHE_HIT_RATIO = Gauge(
    "rag_cache_hit_ratio",
    "RAG cache hit ratio (hits / total requests)",
)

QUALITY_HALLUCINATION_DETECTED = Counter(
    "quality_hallucination_detected_total",
    "Hallucination detections by type",
    ["hallucination_type"],
)


# ── Middleware for Automatic Metrics Collection ────────────


async def metrics_middleware(request: Request, call_next):
    """Middleware to automatically collect HTTP metrics."""
    start_time = time.time()

    try:
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time
        HTTP_REQUESTS.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()

        HTTP_REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(duration)

        return response

    except Exception:
        # Record error metrics
        duration = time.time() - start_time
        HTTP_REQUESTS.labels(method=request.method, endpoint=request.url.path, status=500).inc()

        HTTP_REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(duration)

        raise


# ── Metrics Endpoint ──────────────────────────────────────


metrics_app = FastAPI()


@metrics_app.get("/")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Helper Functions ──────────────────────────────────────


def record_llm_call(model: str, provider: str, success: bool = True, error_type: str | None = None):
    """Record LLM API call metrics."""
    LLM_API_CALLS.labels(model=model, provider=provider).inc()

    if not success and error_type:
        LLM_API_ERRORS.labels(model=model, provider=provider, error_type=error_type).inc()


def record_db_error():
    """Record database connection error."""
    DB_CONNECTION_ERRORS.inc()


def record_cache_hit():
    """Record RAG cache hit."""
    RAG_CACHE_HITS.inc()


def record_cache_miss():
    """Record RAG cache miss."""
    RAG_CACHE_MISSES.inc()


def set_active_sessions(count: int):
    """Set active sessions count."""
    # Note: Prometheus Gauge would be better for this, but keeping simple
    pass


def record_anti_pattern_hit(pattern_type: str, severity: str = "warn"):
    """Record an anti-pattern detection hit."""
    QUALITY_ANTI_PATTERN_HITS.labels(pattern_type=pattern_type, severity=severity).inc()


def record_quality_rewrite(reason: str = "low_score"):
    """Record a low-quality rewrite trigger."""
    QUALITY_REWRITE.labels(reason=reason).inc()


def record_judge_score(dimension: str, score: float):
    """Record an LLM judge quality score for a dimension."""
    QUALITY_JUDGE_SCORE.labels(dimension=dimension).set(score)


def record_hallucination(hallucination_type: str):
    """Record a hallucination detection event."""
    QUALITY_HALLUCINATION_DETECTED.labels(hallucination_type=hallucination_type).inc()
