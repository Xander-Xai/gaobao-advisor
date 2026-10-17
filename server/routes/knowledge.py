"""Knowledge search endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query
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

    Returns ``has_evidence=false`` with an empty result when the corpus is
    healthy but holds nothing relevant. Returns HTTP 503 when retrieval is
    disabled or broken, so a caller cannot mistake "unavailable" for "no match".
    """
    try:
        result = rag.search(
            request.query,
            slots={"groups": request.groups} if request.groups else None,
        )
    except rag.RagError as e:
        status = rag.status()
        logger.warning("Knowledge search unavailable (%s): %s", status["state"], e)
        raise HTTPException(status_code=503, detail={"state": status["state"], "reason": status["reason"]}) from e
    return {
        "count": len(result.get("group_chunks", [])),
        "has_evidence": bool(result.get("has_evidence")),
        "groups": result.get("groups", []),
        "chunks": result.get("group_chunks", []),
        "citations": result.get("citations", []),
        "quotes": result.get("quotes", []),
    }


@router.get("/quotes")
async def get_quotes(
    major: str | None = Query(None, description="专业名称"),
    top_k: int = Query(5, ge=1, le=20),
):
    """Get knowledge quotes, optionally filtered by major.

    The public demo ships no attributed-quote corpus, so this normally returns
    an empty list; that is "no quotes available", not an error.
    """
    try:
        result = rag.search(major or "", slots={"interest": major} if major else None)
    except rag.RagError as e:
        status = rag.status()
        logger.warning("Quote lookup unavailable (%s): %s", status["state"], e)
        raise HTTPException(status_code=503, detail={"state": status["state"], "reason": status["reason"]}) from e
    quotes = result.get("quotes", [])[:top_k]
    return {"count": len(quotes), "quotes": quotes}
