"""Graph node for post-generation quality check."""

from server.services.quality import QualityOrchestrator


def quality_post_check_node(state: dict) -> dict:
    """Run post-generation quality checks on AI output."""
    reply = state.get("reply", "")
    if not reply:
        return {"anti_pattern_violations": [], "should_rewrite": False}

    qc = QualityOrchestrator()
    result = qc.run_post_generation_checks(
        reply,
        bool(state.get("slots", {}).get("family_known", False)),
    )

    return {
        "anti_pattern_violations": result["anti_patterns"],
        "should_rewrite": result["should_rewrite"],
    }
