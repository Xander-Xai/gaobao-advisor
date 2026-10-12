"""Health check endpoint.

Public demo behaviour: the endpoint reports the real state of every optional
subsystem. A disabled knowledge subsystem is reported explicitly as
``RAG_DISABLED`` rather than being folded into a generic ``ok`` — a system
that cannot retrieve evidence must never present itself as fully healthy.
"""

from fastapi import APIRouter

from db.database import is_db_connected
from server import __version__
from server.services import rag

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health_check():
    """Liveness probe with DB status and optional-subsystem state.

    ``status`` is ``ok`` only when required dependencies are healthy.
    ``optional_services`` reports each optional subsystem separately so a
    caller can tell "working" apart from "degraded".
    """
    db_status = "connected" if is_db_connected() else "disconnected"
    rag_status = rag.status()

    optional_services = {
        "rag": {
            "state": rag_status["state"],
            "reason": rag_status["reason"],
            "corpus_configured": rag_status["corpus_configured"],
        },
    }

    degraded = [name for name, s in optional_services.items() if s["state"] != "RAG_ENABLED"]

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "version": __version__,
        "database": db_status,
        "data_profile": "SYNTHETIC_DEMO",
        "optional_services": optional_services,
        "degraded_services": degraded,
    }
