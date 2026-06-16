"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import __version__
from server.metrics import metrics_app, metrics_middleware
from server.middleware.csp import CSPMiddleware
from server.middleware.ratelimit import RateLimitMiddleware
from server.middleware.security import SecurityMiddleware
from server.monitoring import init_sentry
from server.routes.chat import router as chat_router
from server.routes.data import router as data_router
from server.routes.health import router as health_router
from server.routes.knowledge import router as knowledge_router
from server.routes.onboarding import router as onboarding_router
from server.routes.profile import router as profile_router
from server.routes.voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_sentry()

    from db.database import init_db

    init_db()

    # Initialize RAG with knowledge base paths
    from server.services.rag import configure as configure_rag

    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _groups_dir = os.path.join(_project_root, "knowledge", "groups")
    _quotes_dir = os.path.join(_project_root, "knowledge", "quotes")
    if os.path.isdir(_groups_dir):
        configure_rag(groups_dir=_groups_dir, quotes_path=_quotes_dir)
    else:
        import logging

        logging.getLogger(__name__).warning("Knowledge groups dir not found: %s — RAG disabled", _groups_dir)

    yield


app = FastAPI(
    title="gaobao-advisor",
    description="AI 高考志愿顾问 — 考研规划 — 职业方向",
    version=__version__,
    lifespan=lifespan,
)

# ── CORS Configuration ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security Middleware ───────────────────────────────────
app.add_middleware(SecurityMiddleware)

# ── CSP Middleware (nonce-based) ──────────────────────────
app.add_middleware(CSPMiddleware)

# ── Rate Limiting Middleware ──────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── Prometheus Metrics Middleware ─────────────────────────
app.middleware("http")(metrics_middleware)

# ── Mount Prometheus Metrics Endpoint ─────────────────────
app.mount("/metrics", metrics_app)

# ── Include Routers ───────────────────────────────────────
app.include_router(health_router)
app.include_router(onboarding_router)
app.include_router(chat_router)
app.include_router(profile_router)
app.include_router(data_router)
app.include_router(knowledge_router)
app.include_router(voice_router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "gaobao-advisor",
        "version": __version__,
        "docs": "/docs",
        "metrics": "/metrics",
    }
