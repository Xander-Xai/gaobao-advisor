"""Knowledge search endpoints."""
import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel

from server.services import rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeSearchRequest(BaseModel):
    query: str
    groups: list[str] | None = None
    top_k: int = 5


@router.post("/search")
async def search_knowledge(request: KnowledgeSearchRequest):
    """Search the knowledge base for relevant content.

    Returns empty results when RAG is not configured (e.g. during tests).
    """
    try:
        result = rag.search(
            request.query,
            slots={"groups": request.groups} if request.groups else None,
        )
    except (FileNotFoundError, RuntimeError, OSError) as e:
        logger.warning("RAG not configured, returning empty results: %s", e)
        return {"count": 0, "groups": [], "chunks": [], "quotes": []}
    return {
        "count": len(result.get("group_chunks", [])),
        "groups": result.get("groups", []),
        "chunks": result.get("group_chunks", []),
        "quotes": result.get("quotes", []),
    }


@router.get("/quotes")
async def get_quotes(
    major: str | None = Query(None, description="专业名称"),
    top_k: int = Query(5, ge=1, le=20),
):
    """Get expert quotes, optionally filtered by major.

    Returns empty results when RAG is not configured (e.g. during tests).
    """
    try:
        result = rag.search(major or "", slots={"interest": major} if major else None)
    except (FileNotFoundError, RuntimeError, OSError) as e:
        logger.warning("RAG not configured, returning empty quotes: %s", e)
        return {"count": 0, "quotes": []}
    quotes = result.get("quotes", [])[:top_k]
    return {"count": len(quotes), "quotes": quotes}
