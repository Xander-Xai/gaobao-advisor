"""Health check endpoint."""

from fastapi import APIRouter

from db.database import is_db_connected
from server import __version__

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health_check():
    """Basic liveness probe with DB status."""
    db_status = "connected" if is_db_connected() else "disconnected"
    return {
        "status": "ok",
        "version": __version__,
        "database": db_status,
    }
