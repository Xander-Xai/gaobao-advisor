"""scorecard — 评分卡定义和聚合逻辑。

定义 LLM-as-Judge 评估的维度权重、评分数据结构和聚合算法。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 维度权重 ────────────────────────────────────────────────────────
DIMENSION_WEIGHTS: dict[str, float] = {
    "factual": 0.40,
    "relevance": 0.25,
    "helpfulness": 0.25,
    "style": 0.10,
}

# ── 等级阈值 ────────────────────────────────────────────────────────
EXCELLENT_THRESHOLD = 85
FAIL_THRESHOLD = 60

# ── 缺失维度默认分 ─────────────────────────────────────────────────
_MISSING_DEFAULT = 50.0


@dataclass(frozen=True)
class DimensionScore:
    """单个维度的评分结果。"""

    dimension: str
    score: float = 0.0
    reason: str = ""
    issues: list[str] = field(default_factory=list)
    unscored: bool = False


@dataclass(frozen=True)
class JudgeResult:
    """LLM-as-Judge 完整评估结果。"""

    scores: dict[str, float]
    aggregate_score: float
    dimensions: list[DimensionScore]
    hallucination_flags: list[str]
    judge_model: str
    latency_ms: int

    @property
    def grade(self) -> str:
        """根据聚合分数返回等级: excellent / pass / fail。"""
        if self.aggregate_score >= EXCELLENT_THRESHOLD:
            return "excellent"
        if self.aggregate_score >= FAIL_THRESHOLD:
            return "pass"
        return "fail"

    @property
    def should_rewrite(self) -> bool:
        """是否需要重写回答。"""
        return self.aggregate_score < FAIL_THRESHOLD or len(self.hallucination_flags) > 0


def compute_aggregate(scores: dict[str, float]) -> float:
    """计算加权聚合分数。

    缺失维度使用默认分 50，确保结果始终可计算。

    Args:
        scores: 维度名 -> 分数 (0-100) 的映射。

    Returns:
        加权平均分 (0-100)。
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for dim, weight in DIMENSION_WEIGHTS.items():
        score = scores.get(dim, _MISSING_DEFAULT)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return _MISSING_DEFAULT

    return round(weighted_sum / total_weight, 2)
