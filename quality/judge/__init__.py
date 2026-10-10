"""judge — LLM-as-Judge 质量评估系统。

提供基于 LLM 的多维度质量评估和幻觉检测能力。

用法:
    from quality.judge import QualityJudge

    judge = QualityJudge()
    result = await judge.evaluate(
        query="680分能上什么大学？",
        reply="680分可以报考清华大学...",
        context={"knowledge_chunks": "..."},
    )
    print(result.grade)        # excellent / pass / fail
    print(result.should_rewrite)  # True / False
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from quality.judge.hallucination import HallucinationDetector
from quality.judge.judge_router import JudgeRouter
from quality.judge.scorecard import (
    DIMENSION_WEIGHTS,
    DimensionScore,
    JudgeResult,
    compute_aggregate,
)

logger = logging.getLogger(__name__)


class QualityJudge:
    """LLM-as-Judge 质量评估器。

    协调维度评分和幻觉检测，输出完整的评估结果。
    """

    def __init__(self, model_name: str | None = None) -> None:
        """初始化评估器。

        Args:
            model_name: 评分使用的 LLM 模型名称。为 None 时从配置加载。
        """
        self._router = JudgeRouter(model_name=model_name)
        self._hallucination_detector = HallucinationDetector()

    def _fallback_result(
        self,
        query: str,
        reply: str,
        context: dict[str, Any] | None,
        reason: str,
        start_time: float | None = None,
    ) -> JudgeResult:
        """Build a non-blocking fallback result when async judging is unavailable."""
        start_time = start_time or time.monotonic()
        context = context or {}
        knowledge_chunks = context.get("knowledge_chunks")
        dimensions = [
            DimensionScore(dimension=dim, score=50.0, reason=reason, unscored=True) for dim in DIMENSION_WEIGHTS
        ]
        scores = {d.dimension: d.score for d in dimensions}
        hallucination_flags = self._hallucination_detector.detect(
            reply=reply,
            query=query,
            knowledge_chunks=knowledge_chunks,
        )
        return JudgeResult(
            scores=scores,
            aggregate_score=compute_aggregate(scores),
            dimensions=dimensions,
            hallucination_flags=hallucination_flags,
            judge_model=self._router.model_name,
            latency_ms=int((time.monotonic() - start_time) * 1000),
        )

    async def evaluate(
        self,
        query: str,
        reply: str,
        context: dict[str, Any] | None = None,
    ) -> JudgeResult:
        """评估 AI 回答的质量。

        1. 并行调用 JudgeRouter 评估 4 个维度
        2. 调用 HallucinationDetector 检测幻觉
        3. 计算聚合分数
        4. 返回 JudgeResult

        Args:
            query: 用户原始问题。
            reply: AI 生成的回答。
            context: 评估上下文，可包含:
                - knowledge_chunks: 知识库参考文本
                - conversation_history: 对话历史

        Returns:
            JudgeResult 完整评估结果。
        """
        start_time = time.monotonic()
        context = context or {}

        knowledge_chunks = context.get("knowledge_chunks")
        conversation_history = context.get("conversation_history")

        try:
            # 1. 并行评估所有维度
            dimensions = await self._router.evaluate_all(
                query=query,
                reply=reply,
                knowledge_chunks=knowledge_chunks,
                conversation_history=conversation_history,
            )
        finally:
            await self._router.aclose()

        # 2. 幻觉检测
        hallucination_flags = self._hallucination_detector.detect(
            reply=reply,
            query=query,
            knowledge_chunks=knowledge_chunks,
        )

        # 3. 计算聚合分数
        scores = {d.dimension: d.score for d in dimensions}
        aggregate_score = compute_aggregate(scores)

        # 4. 计算延迟
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return JudgeResult(
            scores=scores,
            aggregate_score=aggregate_score,
            dimensions=dimensions,
            hallucination_flags=hallucination_flags,
            judge_model=self._router.model_name,
            latency_ms=elapsed_ms,
        )

    def evaluate_sync(
        self,
        query: str,
        reply: str,
        context: dict[str, Any] | None = None,
    ) -> JudgeResult:
        """同步版本的评估方法。

        在没有事件循环的场景下使用，内部创建临时事件循环。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            logger.warning("QualityJudge.evaluate_sync called inside a running event loop; using fallback scores")
            return self._fallback_result(
                query=query,
                reply=reply,
                context=context,
                reason="评估器处于运行中的事件循环，已降级为默认评分",
            )
        else:
            return asyncio.run(self.evaluate(query, reply, context))
