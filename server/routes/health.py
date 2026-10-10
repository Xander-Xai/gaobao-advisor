"""Health check endpoint."""

from fastapi import APIRouter

from config.loader import load_llm_config, load_runtime_settings
from db.database import is_db_connected
from server import __version__

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health_check():
    """Liveness probe with core and optional-service state."""
    db_status = "connected" if is_db_connected() else "disconnected"
    runtime = load_runtime_settings()
    llm_config = load_llm_config()
    provider = llm_config.get("provider", "unknown")
    return {
        "status": "ok",
        "version": __version__,
        "database": db_status,
        "mode": "demo" if provider == "demo" else runtime["app_env"],
        "llm_provider": provider,
        "optional_services": {
            "rag": "enabled" if runtime["rag_enabled"] else "disabled",
            "voice": "enabled" if runtime["voice_enabled"] else "disabled",
        },
    }
