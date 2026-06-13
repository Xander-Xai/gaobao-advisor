"""FastAPI application entry point."""
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
from server.routes.voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    from db.database import init_db
    init_db()
    yield


app = FastAPI(
    title="gaobao-advisor",
    description="AI 高考志愿顾问 — 考研规划 — 职业方向",
    version=__version__,
    lifespan=lifespan,
)

# CORS first (will be innermost = last to process response)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Security (middle)
app.add_middleware(SecurityMiddleware)
# Rate limit (outermost = first to inspect request)
app.add_middleware(RateLimitMiddleware, rate=20, capacity=40)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(onboarding_router)
app.include_router(data_router)
app.include_router(knowledge_router)
app.include_router(voice_router)
