"""RAG retrieval node.

Public demo behaviour (fail-closed / honest degradation):

The public deployment ships **without** a knowledge corpus. Rather than
swallowing the error and returning an empty ``knowledge_context`` — which
downstream code would happily pass to the LLM as "no knowledge available" —
this node records an explicit ``rag_state`` on the graph state. Downstream
rendering and the ``/api/v1/health`` endpoint both surface that value, so a
disabled RAG stack can never be reported as a working one.
"""

from __future__ import annotations

import logging
from typing import Any

from server.services import rag

logger = logging.getLogger(__name__)


def rag_retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch knowledge chunks and expert quotes, or report why it could not.

    Returns:
        A partial state update. ``rag_state`` is one of ``RAG_ENABLED`` or
        ``RAG_DISABLED``; ``rag_reason`` explains a disabled state.
    """
    text = state.get("input_text", "")
    slots = state.get("slots", {})

    trace = list(state.get("trace", []))

    if not rag.is_available():
        reason = rag.status()["reason"]
        logger.warning("RAG disabled, skipping retrieval: %s", reason)
        trace.append({"node": "rag_retrieve", "event": "RAG_DISABLED", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_DISABLED",
            "rag_reason": reason,
            "trace": trace,
        }

    try:
        search_result = rag.search(text, slots)
    except rag.RagDisabledError:
        reason = rag.status()["reason"]
        logger.warning("RAG became unavailable mid-request: %s", reason)
        trace.append({"node": "rag_retrieve", "event": "RAG_DISABLED", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_DISABLED",
            "rag_reason": reason,
            "trace": trace,
        }
    except Exception as exc:
        reason = f"retrieval error: {exc.__class__.__name__}"
        logger.exception("RAG retrieval failed")
        trace.append({"node": "rag_retrieve", "event": "RAG_ERROR", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_DISABLED",
            "rag_reason": reason,
            "trace": trace,
        }

    rag_chunks: list[dict] = search_result.get("group_chunks", [])
    expert_quotes: list[dict] = search_result.get("quotes", [])

    knowledge_context = ""
    if rag_chunks:
        parts = []
        for chunk in rag_chunks[:5]:
            section = chunk.get("section_title", "")
            content = chunk.get("text", "")
            parts.append(f"[{section}] {content}" if section else content)
        knowledge_context = "\n\n".join(parts)

    trace.append(
        {
            "node": "rag_retrieve",
            "event": f"chunks={len(rag_chunks)},quotes={len(expert_quotes)}",
        }
    )

    return {
        "rag_chunks": rag_chunks,
        "expert_quotes": expert_quotes,
        "knowledge_context": knowledge_context,
        "rag_state": "RAG_ENABLED",
        "rag_reason": "",
        "trace": trace,
    }
