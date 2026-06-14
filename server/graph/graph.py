"""LangGraph advisor graph — wires nodes into a compiled pipeline.

NOTE: The llm_reason node has been removed from the graph.
LLM streaming is handled directly by the SSE handler in chat.py
to avoid double LLM calls. The graph stops at structure_output
(complete path) or question_generate (incomplete path),
and the SSE handler streams tokens from llm_node_stream.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from server.graph.state import AdvisorState
from server.graph.nodes.security_scan import security_scan_node
from server.graph.nodes.intent import intent_detect_node
from server.graph.nodes.route import scene_route_node
from server.graph.nodes.extract import slot_extract_node
from server.graph.nodes.check import profile_check_node
from server.graph.nodes.question import question_generate_node
from server.graph.nodes.quality_nodes import quality_orchestrate_node
from server.graph.nodes.data_nodes import data_query_node
from server.graph.nodes.rag_node import rag_retrieve_node
from server.graph.nodes.reason import reason_node
from server.graph.nodes.structure import structure_output_node
from server.graph.nodes.render import render_reply_node
from server.graph.nodes.memory import memory_node as memory_update_node


def _profile_has_data(state: AdvisorState) -> str:
    """Routing function: complete profile goes to quality pipeline,
    incomplete profile goes to question generation."""
    if state.get("reply"):
        return "has_reply"
    missing = state.get("missing_fields", [])
    if not missing:
        return "complete"
    return "incomplete"


def build_advisor_graph():
    """Build and compile the advisor StateGraph."""
    graph = StateGraph(AdvisorState)

    # ── Register nodes (llm_reason removed) ─────────────────────
    graph.add_node("security_scan", security_scan_node)
    graph.add_node("intent_detect", intent_detect_node)
    graph.add_node("scene_route", scene_route_node)
    graph.add_node("slot_extract", slot_extract_node)
    graph.add_node("profile_check", profile_check_node)
    graph.add_node("question_generate", question_generate_node)
    graph.add_node("quality_orchestrate", quality_orchestrate_node)
    graph.add_node("data_query", data_query_node)
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("structure_output", structure_output_node)
    graph.add_node("render_reply", render_reply_node)
    graph.add_node("memory_update", memory_update_node)

    # ── Entry point ───────────────────────────────────────────
    graph.set_entry_point("security_scan")

    # ── Linear chain up to profile_check ──────────────────────
    graph.add_edge("security_scan", "intent_detect")
    graph.add_edge("intent_detect", "scene_route")
    graph.add_edge("scene_route", "slot_extract")
    graph.add_edge("slot_extract", "profile_check")

    # ── Conditional edge from profile_check ───────────────────
    graph.add_conditional_edges(
        "profile_check",
        _profile_has_data,
        {
            "complete": "quality_orchestrate",
            "incomplete": "question_generate",
            "has_reply": "render_reply",
        },
    )

    # ── Question path converges to render → memory → END ───────
    graph.add_edge("question_generate", "render_reply")

    # ── Full pipeline: structure_output → render (no llm_reason) ──
    graph.add_edge("quality_orchestrate", "data_query")
    graph.add_edge("data_query", "rag_retrieve")
    graph.add_edge("rag_retrieve", "reason")
    graph.add_edge("reason", "structure_output")
    graph.add_edge("structure_output", "render_reply")

    # ── Converge: render → memory → END ───────────────────────
    graph.add_edge("render_reply", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


# ── Singleton accessor ────────────────────────────────────────
_advisor_graph = None


def get_advisor_graph():
    """Return the compiled graph (lazy singleton)."""
    global _advisor_graph
    if _advisor_graph is None:
        _advisor_graph = build_advisor_graph()
    return _advisor_graph
