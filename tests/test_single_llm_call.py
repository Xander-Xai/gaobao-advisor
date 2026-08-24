"""Verify that the graph stops before LLM and SSE handler streams tokens directly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.graph.graph import build_advisor_graph


def test_graph_does_not_contain_llm_reason_node():
    """The compiled graph should not have an llm_reason node."""
    graph = build_advisor_graph()
    node_names = list(graph.get_graph().nodes)
    assert "llm_reason" not in node_names, f"Graph still contains llm_reason node: {node_names}"


def test_graph_complete_path_ends_at_structure_output():
    """The complete-profile pre-generation path should stop after structure_output."""
    graph = build_advisor_graph()
    compiled = graph.get_graph()
    edges_from_structure = [e for e in compiled.edges if e.source == "structure_output"]
    assert len(edges_from_structure) == 1
    assert edges_from_structure[0].target == "__end__", (
        f"structure_output should connect to __end__, got: {edges_from_structure[0].target}"
    )
