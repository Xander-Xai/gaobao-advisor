"""Graph node for feedback collection and rewrite trigger."""


def feedback_node(state: dict) -> dict:
    """Collect quality data and trigger rewrite if needed."""
    result = {"rewrite_attempts": state.get("rewrite_attempts", 0)}

    grade = state.get("quality_grade", "")
    should_rewrite = state.get("should_rewrite", False)

    if grade == "fail" or should_rewrite:
        from server.metrics import record_quality_rewrite

        record_quality_rewrite("low_score")
        result["needs_rewrite"] = True

    return result
