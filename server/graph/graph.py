"""LangGraph advisor pipelines for pre- and post-generation processing.

The chat endpoint owns token streaming. The pre-generation graph prepares all
state required by the LLM and stops before a final answer is rendered. The
post-generation graph runs only after a final reply exists, so quality checks
and persistence observe the actual answer shown to the user.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from server.graph.nodes.check import profile_check_node
from server.graph.nodes.data_nodes import data_query_node
from server.graph.nodes.extract import slot_extract_node
from server.graph.nodes.feedback_node import feedback_node
from server.graph.nodes.intent import intent_detect_node
from server.graph.nodes.judge_node import quality_judge_node
from server.graph.nodes.memory import memory_node as memory_update_node
from server.graph.nodes.post_check import quality_post_check_node
from server.graph.nodes.quality_nodes import quality_orchestrate_node
from server.graph.nodes.question import question_generate_node
from server.graph.nodes.rag_node import rag_retrieve_node
from server.graph.nodes.reason import reason_node
from server.graph.nodes.route import scene_route_node
from server.graph.nodes.security_scan import security_scan_node
from server.graph.nodes.source_attribution import source_attribution_node
from server.graph.nodes.structure import structure_output_node
from server.graph.state import AdvisorState


def _profile_has_data(state: AdvisorState) -> str:
    """Route complete profiles to retrieval and incomplete profiles to questioning."""
    if state.get("reply"):
        return "has_reply"
    if not state.get("missing_fields", []):
        return "complete"
    return "incomplete"


def build_advisor_graph():
    """Build the pre-generation graph used before SSE token streaming."""
    graph = StateGraph(AdvisorState)

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

    graph.set_entry_point("security_scan")
    graph.add_edge("security_scan", "intent_detect")
    graph.add_edge("intent_detect", "scene_route")
    graph.add_edge("scene_route", "slot_extract")
    graph.add_edge("slot_extract", "profile_check")

    graph.add_conditional_edges(
        "profile_check",
        _profile_has_data,
        {
            "complete": "quality_orchestrate",
            "incomplete": "question_generate",
            "has_reply": END,
        },
    )

    graph.add_edge("question_generate", END)
    graph.add_edge("quality_orchestrate", "data_query")
    graph.add_edge("data_query", "rag_retrieve")
    graph.add_edge("rag_retrieve", "reason")
    graph.add_edge("reason", "structure_output")
    graph.add_edge("structure_output", END)

    return graph.compile()


def build_post_generation_graph():
    """Build the graph that runs after the final assistant reply is generated."""
    graph = StateGraph(AdvisorState)

    graph.add_node("source_attribution", source_attribution_node)
    graph.add_node("quality_post_check", quality_post_check_node)
    graph.add_node("quality_judge", quality_judge_node)
    graph.add_node("feedback", feedback_node)
    graph.add_node("memory_update", memory_update_node)

    graph.set_entry_point("source_attribution")
    graph.add_edge("source_attribution", "quality_post_check")
    graph.add_edge("quality_post_check", "quality_judge")
    graph.add_edge("quality_judge", "feedback")
    graph.add_edge("feedback", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


_advisor_graph = None
_post_generation_graph = None


def get_advisor_graph():
    """Return the lazy singleton pre-generation graph."""
    global _advisor_graph
    if _advisor_graph is None:
        _advisor_graph = build_advisor_graph()
    return _advisor_graph


def get_post_generation_graph():
    """Return the lazy singleton post-generation graph."""
    global _post_generation_graph
    if _post_generation_graph is None:
        _post_generation_graph = build_post_generation_graph()
    return _post_generation_graph
