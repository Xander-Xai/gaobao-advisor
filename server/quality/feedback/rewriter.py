"""Reply rewriter — attempts to improve low-quality AI replies."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_REWRITE_ATTEMPTS = 2
BASE_DELAY = 1.0  # seconds between attempts


@dataclass(frozen=True)
class RewriteRecord:
    """Record of a single rewrite attempt."""

    rewrite_id: str
    original_reply: str
    original_score: float
    attempt: int
    rewritten_reply: str | None = None
    rewritten_score: float | None = None
    success: bool = False
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class ReplyRewriter:
    """Attempts to rewrite low-quality AI replies via LLM correction."""

    def rewrite(
        self,
        original_reply: str,
        query: str,
        original_score: float,
        violations: list[dict],
        hallucination_flags: list,
        context: dict | None = None,
    ) -> tuple[str, float]:
        """Try to rewrite a low-quality reply.

        Makes up to ``MAX_REWRITE_ATTEMPTS`` calls to the LLM with a
        correction prompt.  On success returns (rewritten_text, new_score).
        If all attempts fail, returns (original_reply, original_score).
        """
        records: list[RewriteRecord] = []

        for attempt in range(1, MAX_REWRITE_ATTEMPTS + 1):
            rid = str(uuid.uuid4())[:8]
            try:
                messages = self._build_correction_prompt(
                    query, original_reply, original_score, violations, hallucination_flags,
                )
                rewritten = self._call_llm_for_rewrite(messages)

                # Placeholder scoring: in production the rewritten text
                # would be re-evaluated by the quality judge.  For now
                # we assume a modest improvement if the LLM call succeeds.
                rewritten_score = min(original_score + 0.1, 1.0)

                record = RewriteRecord(
                    rewrite_id=rid,
                    original_reply=original_reply,
                    original_score=original_score,
                    attempt=attempt,
                    rewritten_reply=rewritten,
                    rewritten_score=rewritten_score,
                    success=True,
                )
                records.append(record)
                logger.info(
                    "Rewrite attempt %d/%d succeeded (score %.2f -> %.2f)",
                    attempt,
                    MAX_REWRITE_ATTEMPTS,
                    original_score,
                    rewritten_score,
                )
                return rewritten, rewritten_score

            except NotImplementedError:
                # LLM client not yet wired — bail out immediately
                logger.warning("Rewrite skipped: LLM client not implemented")
                return original_reply, original_score

            except Exception as exc:
                record = RewriteRecord(
                    rewrite_id=rid,
                    original_reply=original_reply,
                    original_score=original_score,
                    attempt=attempt,
                    success=False,
                    error=str(exc),
                )
                records.append(record)
                logger.warning(
                    "Rewrite attempt %d/%d failed: %s",
                    attempt,
                    MAX_REWRITE_ATTEMPTS,
                    exc,
                )
                if attempt < MAX_REWRITE_ATTEMPTS:
                    time.sleep(BASE_DELAY * attempt)

        # All attempts exhausted — return original
        logger.error(
            "All %d rewrite attempts failed for query='%s'",
            MAX_REWRITE_ATTEMPTS,
            query[:50],
        )
        return original_reply, original_score

    # ── Internal helpers ──────────────────────────────────────────

    def _build_correction_prompt(
        self,
        query: str,
        original_reply: str,
        original_score: float,
        violations: list[dict],
        hallucination_flags: list,
    ) -> list[dict]:
        """Build the LLM prompt that asks for a corrected reply."""
        violation_text = "\n".join(
            f"- {v.get('pattern', v) if isinstance(v, dict) else v}"
            for v in violations
        ) or "无"
        hallucination_text = "\n".join(
            f"- {h}" for h in hallucination_flags
        ) or "无"

        system_msg = (
            "你是一个高考志愿填报AI回复质量修正专家。"
            "你的任务是根据质量评估结果，修正低质量的AI回复。"
            "修正时必须：\n"
            "1. 解决所有违反质量规则的问题\n"
            "2. 消除幻觉标记的内容\n"
            "3. 保持回复的专业性和准确性\n"
            "4. 不引入新的问题\n"
        )

        user_msg = (
            f"原始用户问题：{query}\n\n"
            f"原始AI回复（质量分 {original_score:.2f}）：\n{original_reply}\n\n"
            f"质量违规项：\n{violation_text}\n\n"
            f"幻觉标记：\n{hallucination_text}\n\n"
            "请修正以上回复，解决所有质量问题。"
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _call_llm_for_rewrite(self, messages: list[dict]) -> str:
        """Call the LLM to generate a rewritten reply.

        Placeholder — raises NotImplementedError until the project's
        LLM client is wired in.
        """
        raise NotImplementedError(
            "LLM client for rewrite not yet integrated. "
            "Wire in the project's LLM client to enable rewrites."
        )
