"""Test quality post-check node."""

from server.graph.nodes.post_check import quality_post_check_node


class TestQualityPostCheckNode:
    def test_empty_reply_returns_no_violations(self):
        """Empty reply should short-circuit with no violations."""
        result = quality_post_check_node({"reply": ""})
        assert result["anti_pattern_violations"] == []
        assert result["should_rewrite"] is False

    def test_clean_reply_passes(self):
        """A concrete, non-vague reply should pass all checks."""
        result = quality_post_check_node({
            "reply": "根据你的分数，建议冲刺江苏的院校，稳妥选择山东的。",
        })
        violations = result["anti_pattern_violations"]
        error_count = sum(1 for v in violations if v.get("severity") == "error")
        assert error_count == 0

    def test_follow_passion_triggers_rewrite_when_family_unknown(self):
        """Rule 2 (未问家庭即给热爱建议) should trigger rewrite when family_known is False."""
        result = quality_post_check_node({
            "reply": "追随你的热爱，选择你最感兴趣的专业方向。",
            "slots": {"family_known": False},
        })
        assert result["should_rewrite"] is True

    def test_follow_passion_allowed_when_family_known(self):
        """Rule 2 should be skipped when family is already known."""
        result = quality_post_check_node({
            "reply": "追随你的热爱，选择你最感兴趣的专业方向。",
            "slots": {"family_known": True},
        })
        # Should not trigger anti-pattern 2 since family is known
        violations = result["anti_pattern_violations"]
        error_count = sum(1 for v in violations if v.get("severity") == "error")
        assert error_count == 0

    def test_vague_judgment_triggers_rewrite(self):
        """Rule 1 (模糊判断) should trigger rewrite."""
        result = quality_post_check_node({
            "reply": "这个问题因人而异，需要综合考虑你的各方面情况。",
        })
        assert result["should_rewrite"] is True

    def test_missing_reply_key_returns_empty(self):
        """Missing 'reply' key should be handled gracefully."""
        result = quality_post_check_node({})
        assert result["anti_pattern_violations"] == []
        assert result["should_rewrite"] is False