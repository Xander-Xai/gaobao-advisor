"""test_scorecard — 评分卡聚合逻辑和等级分类测试。"""

from __future__ import annotations

from quality.judge.scorecard import (
    DIMENSION_WEIGHTS,
    EXCELLENT_THRESHOLD,
    FAIL_THRESHOLD,
    DimensionScore,
    JudgeResult,
    compute_aggregate,
)


class TestComputeAggregate:
    """compute_aggregate 函数测试。"""

    def test_all_dimensions_present(self) -> None:
        """所有维度都有分数时，计算加权平均。"""
        scores = {
            "factual": 90,
            "relevance": 80,
            "helpfulness": 75,
            "style": 85,
        }
        result = compute_aggregate(scores)
        expected = 90 * 0.40 + 80 * 0.25 + 75 * 0.25 + 85 * 0.10
        assert result == round(expected, 2)

    def test_missing_dimension_defaults_to_50(self) -> None:
        """缺失维度使用默认分 50。"""
        scores = {"factual": 90}
        result = compute_aggregate(scores)
        # factual: 90*0.40, relevance: 50*0.25, helpfulness: 50*0.25, style: 50*0.10
        expected = 90 * 0.40 + 50 * 0.25 + 50 * 0.25 + 50 * 0.10
        assert result == round(expected, 2)

    def test_all_dimensions_missing(self) -> None:
        """所有维度缺失时，返回默认分 50。"""
        scores: dict[str, float] = {}
        result = compute_aggregate(scores)
        assert result == 50.0

    def test_extra_dimensions_ignored(self) -> None:
        """额外的维度不影响结果。"""
        scores = {
            "factual": 100,
            "relevance": 100,
            "helpfulness": 100,
            "style": 100,
            "extra": 0,
        }
        result = compute_aggregate(scores)
        assert result == 100.0

    def test_zero_scores(self) -> None:
        """所有维度为 0 分。"""
        scores = {
            "factual": 0,
            "relevance": 0,
            "helpfulness": 0,
            "style": 0,
        }
        result = compute_aggregate(scores)
        assert result == 0.0

    def test_factual_has_highest_weight(self) -> None:
        """事实性维度权重最高，对结果影响最大。"""
        scores_factual_high = {
            "factual": 100,
            "relevance": 0,
            "helpfulness": 0,
            "style": 0,
        }
        scores_relevance_high = {
            "factual": 0,
            "relevance": 100,
            "helpfulness": 0,
            "style": 0,
        }
        factual_result = compute_aggregate(scores_factual_high)
        relevance_result = compute_aggregate(scores_relevance_high)
        assert factual_result > relevance_result

    def test_result_is_float(self) -> None:
        """结果类型为 float。"""
        scores = {"factual": 90, "relevance": 80, "helpfulness": 75, "style": 85}
        result = compute_aggregate(scores)
        assert isinstance(result, float)


class TestDimensionScore:
    """DimensionScore 数据类测试。"""

    def test_default_values(self) -> None:
        """默认值正确。"""
        ds = DimensionScore(dimension="factual")
        assert ds.dimension == "factual"
        assert ds.score == 0.0
        assert ds.reason == ""
        assert ds.issues == []
        assert ds.unscored is False

    def test_custom_values(self) -> None:
        """自定义值正确。"""
        ds = DimensionScore(
            dimension="relevance",
            score=75.0,
            reason="部分偏题",
            issues=["未直接回答核心问题"],
            unscored=False,
        )
        assert ds.dimension == "relevance"
        assert ds.score == 75.0
        assert ds.reason == "部分偏题"
        assert len(ds.issues) == 1
        assert ds.unscored is False

    def test_unscored_dimension(self) -> None:
        """未评分维度的标记正确。"""
        ds = DimensionScore(
            dimension="style",
            score=50,
            reason="评估超时",
            unscored=True,
        )
        assert ds.unscored is True


class TestJudgeResult:
    """JudgeResult 数据类测试。"""

    def _make_result(
        self,
        aggregate_score: float,
        hallucination_flags: list[str] | None = None,
    ) -> JudgeResult:
        """构建测试用 JudgeResult。"""
        return JudgeResult(
            scores={"factual": aggregate_score},
            aggregate_score=aggregate_score,
            dimensions=[DimensionScore(dimension="factual", score=aggregate_score)],
            hallucination_flags=hallucination_flags or [],
            judge_model="test-model",
            latency_ms=100,
        )

    def test_grade_excellent(self) -> None:
        """聚合分 >= 85 为 excellent。"""
        result = self._make_result(85.0)
        assert result.grade == "excellent"

    def test_grade_exclusive_upper(self) -> None:
        """聚合分 90 为 excellent。"""
        result = self._make_result(90.0)
        assert result.grade == "excellent"

    def test_grade_pass(self) -> None:
        """60 <= 聚合分 < 85 为 pass。"""
        result = self._make_result(70.0)
        assert result.grade == "pass"

    def test_grade_pass_at_threshold(self) -> None:
        """聚合分恰好 60 为 pass。"""
        result = self._make_result(60.0)
        assert result.grade == "pass"

    def test_grade_fail(self) -> None:
        """聚合分 < 60 为 fail。"""
        result = self._make_result(50.0)
        assert result.grade == "fail"

    def test_grade_fail_zero(self) -> None:
        """聚合分 0 为 fail。"""
        result = self._make_result(0.0)
        assert result.grade == "fail"

    def test_should_rewrite_low_score(self) -> None:
        """低分需要重写。"""
        result = self._make_result(55.0)
        assert result.should_rewrite is True

    def test_should_rewrite_with_hallucination(self) -> None:
        """有幻觉标记需要重写。"""
        result = self._make_result(90.0, hallucination_flags=["numeric:680"])
        assert result.should_rewrite is True

    def test_should_not_rewrite_good_score_no_hallucination(self) -> None:
        """高分且无幻觉标记不需要重写。"""
        result = self._make_result(85.0)
        assert result.should_rewrite is False

    def test_should_rewrite_pass_score_with_hallucination(self) -> None:
        """及格分数但有幻觉标记仍需重写。"""
        result = self._make_result(70.0, hallucination_flags=["source_missing"])
        assert result.should_rewrite is True


class TestThresholds:
    """阈值常量测试。"""

    def test_excellent_threshold(self) -> None:
        assert EXCELLENT_THRESHOLD == 85

    def test_fail_threshold(self) -> None:
        assert FAIL_THRESHOLD == 60

    def test_weights_sum_to_one(self) -> None:
        """权重总和应为 1.0。"""
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_factual_weight_highest(self) -> None:
        """事实性权重最高。"""
        assert DIMENSION_WEIGHTS["factual"] > DIMENSION_WEIGHTS["relevance"]
        assert DIMENSION_WEIGHTS["factual"] > DIMENSION_WEIGHTS["helpfulness"]
        assert DIMENSION_WEIGHTS["factual"] > DIMENSION_WEIGHTS["style"]
