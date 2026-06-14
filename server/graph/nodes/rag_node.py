"""RAG retrieval node — fetches knowledge chunks and expert quotes."""
from __future__ import annotations

from typing import Any

from server.services import rag


def rag_retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
    """Search the knowledge base for relevant content.

    Uses the RAG service to find knowledge groups, chunks, and expert quotes
    related to the user's query and slots.
    """
    text = state.get("input_text", "")
    slots = state.get("slots", {})

    rag_chunks: list[dict] = []
    expert_quotes: list[dict] = []
    knowledge_context = ""

    try:
        search_result = rag.search(text, slots)
        rag_chunks = search_result.get("group_chunks", [])
        expert_quotes = search_result.get("quotes", [])

        # Build knowledge context string from chunks
        if rag_chunks:
            parts = []
            for chunk in rag_chunks[:5]:
                section = chunk.get("section_title", "")
                content = chunk.get("text", "")
                if section:
                    parts.append(f"[{section}] {content}")
                else:
                    parts.append(content)
            knowledge_context = "\n\n".join(parts)

    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("RAG retrieval failed: %s", exc, exc_info=True)
        # RAG not configured or error — continue without knowledge

    trace = list(state.get("trace", []))
    trace.append({
        "node": "rag_retrieve",
        "event": f"chunks={len(rag_chunks)},quotes={len(expert_quotes)}",
    })

    return {
        "rag_chunks": rag_chunks,
        "expert_quotes": expert_quotes,
        "knowledge_context": knowledge_context,
        "trace": trace,
    }
