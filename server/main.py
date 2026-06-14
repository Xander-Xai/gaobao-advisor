"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import __version__
from server.middleware.ratelimit import RateLimitMiddleware
from server.middleware.security import SecurityMiddleware
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

# CORS: lock down for production, dev-friendly defaults
_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3080,http://localhost:8501,http://localhost:8000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
# Security (middle)
app.add_middleware(SecurityMiddleware)
# Rate limit (outermost = first to inspect request)
app.add_middleware(RateLimitMiddleware, rate=20, capacity=40)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(onboarding_router)
app.include_router(profile_router)
app.include_router(data_router)
app.include_router(knowledge_router)
app.include_router(voice_router)
