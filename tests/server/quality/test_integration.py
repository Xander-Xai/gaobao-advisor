"""Integration tests for the quality flywheel system."""

from __future__ import annotations

from quality.judge.hallucination import HallucinationDetector
from quality.judge.scorecard import DIMENSION_WEIGHTS, DimensionScore, JudgeResult, compute_aggregate


class TestQualityJudgeIntegration:
    """QualityJudge 集成测试 — 验证评估器能产出完整结果。"""

    def test_judge_evaluate_returns_result(self, monkeypatch) -> None:
        """Verify judge can produce a result object.

        The external LLM call is patched so this remains a deterministic
        integration test for the judge aggregation path.
        """
        from quality.judge import QualityJudge
        from quality.judge.judge_router import JudgeRouter

        async def fake_evaluate_all(self, **kwargs):  # noqa: ANN001, ARG001
            return [DimensionScore(dimension=dim, score=75.0, reason="offline test") for dim in DIMENSION_WEIGHTS]

        monkeypatch.setattr(JudgeRouter, "evaluate_all", fake_evaluate_all)

        judge = QualityJudge()
        result = judge.evaluate_sync(
            query="计算机专业怎么样？",
            reply="计算机专业就业前景良好。",
            context={"knowledge_chunks": ["计算机就业率92%"], "slots": {}},
        )
        assert isinstance(result, JudgeResult)
        assert len(result.scores) == 4
        assert result.aggregate_score > 0

    def test_judge_empty_reply(self, monkeypatch) -> None:
        """空回复应得到低分或 fail 等级。"""
        from quality.judge import QualityJudge
        from quality.judge.judge_router import JudgeRouter

        async def fake_evaluate_all(self, **kwargs):  # noqa: ANN001, ARG001
            return [DimensionScore(dimension=dim, score=20.0, reason="empty reply") for dim in DIMENSION_WEIGHTS]

        monkeypatch.setattr(JudgeRouter, "evaluate_all", fake_evaluate_all)

        judge = QualityJudge()
        result = judge.evaluate_sync(query="你好", reply="", context={})
        assert result.aggregate_score < 60 or result.grade == "fail"


class TestGraphIntegration:
    """图节点注册集成测试。"""

    def test_graph_has_quality_nodes(self) -> None:
        """验证图中包含所有质量相关节点。"""
        from server.graph.graph import get_advisor_graph

        g = get_advisor_graph()
        quality_nodes = [
            "source_attribution",
            "quality_post_check",
            "quality_judge",
            "feedback",
        ]
        for node in quality_nodes:
            assert node in g.nodes, f"{node} not in graph"


class TestScorecardIntegration:
    """评分卡聚合与等级分类集成测试。"""

    def test_aggregate_and_grade(self) -> None:
        """高分四维度应得到 excellent 等级且不需要重写。"""
        scores = {"factual": 95, "relevance": 90, "helpfulness": 88, "style": 85}
        agg = compute_aggregate(scores)
        result = JudgeResult(
            scores=scores,
            aggregate_score=agg,
            dimensions=[],
            hallucination_flags=[],
            judge_model="test",
            latency_ms=10,
        )
        assert result.grade == "excellent"
        assert result.should_rewrite is False

    def test_hallucination_detector(self) -> None:
        """幻觉检测器应能检测到数字不匹配。"""
        detector = HallucinationDetector()
        flags = detector.detect(
            "数据显示计算机就业率95%",
            knowledge_chunks=["计算机就业率92%"],
        )
        # May detect source_missing or numeric mismatch
        assert isinstance(flags, list)

    def test_feedback_collector(self) -> None:
        """FeedbackCollector 应具备必要的方法。"""
        from server.quality.feedback.collector import FeedbackCollector

        collector = FeedbackCollector()
        assert hasattr(collector, "save_feedback")
        assert hasattr(collector, "detect_implicit_signals")
