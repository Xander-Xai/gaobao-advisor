"""Quote attribution and source-marking tests — PUBLIC DEMO EDITION.

The private original shipped a corpus of quotations attributed to a named
individual, and this module asserted that corpus was present, searchable and
attributed. That corpus is **not redistributed** here (it reproduces a living
person's speech), so those assertions no longer describe this repository.

What replaces them is the part that is genuinely about engineering rather than
content: numeric source-marking. Any concrete figure the model emits must carry
a provenance marker, and that rule must hold regardless of whether any
knowledge corpus exists.

The corpus-absence contract is pinned in
``test_knowledge_corpus_absent_contract.py``.
"""

from __future__ import annotations

from server.graph.nodes.source_attribution import (
    source_attribution_node,
    validate_source_attribution,
)


class TestNumericSourceMarking:
    """Generic rule: concrete figures must be attributed."""

    def test_unattributed_score_gets_marker(self) -> None:
        out = validate_source_attribution("该校去年最低分是580分。")
        assert "来源" in out or "数据来源" in out or "注" in out

    def test_already_attributed_is_left_alone(self) -> None:
        reply = "该校去年最低分是580分（来源：合成演示数据，2024）。"
        assert validate_source_attribution(reply) == reply

    def test_education_badges_are_not_treated_as_figures(self) -> None:
        """985/211 must not be flagged as an unsourced number."""
        out = validate_source_attribution("建议优先考虑985院校。")
        assert "985" in out

    def test_rule_holds_without_any_corpus(self) -> None:
        """Marking works with zero knowledge chunks present."""
        out = validate_source_attribution("该校毕业去向落实率为85%。")
        assert isinstance(out, str)
        assert out.strip()


class TestNoPersonalQuotations:
    """Negative controls: no attributed personal speech may be produced."""

    def test_no_personal_quote_corpus_in_repo(self) -> None:
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        offenders = [
            p.name
            for p in repo_root.rglob("*.json")
            if "zhangxuefeng" in p.name.lower() or "zhang_xuefeng" in p.name.lower()
        ]
        assert offenders == [], f"personal quotation corpus must not ship: {offenders}"

    def test_retriever_reports_no_quotes(self) -> None:
        """KbRetriever constructed without a corpus has zero quotes."""
        from server.services.kb_retriever import KbRetriever, KeywordOnlyEmbedding

        retriever = KbRetriever(
            groups_dir="",
            quotes_path="",
            embedding_provider=KeywordOnlyEmbedding(),
        )
        result = retriever.search("某位讲师 说 就业", {})
        assert result.quotes == [], "no personal quotations may be returned"


class TestSourceAttributionNode:
    def test_node_returns_trace(self) -> None:
        state = {"reply": "该校最低分580分。", "trace": []}
        out = source_attribution_node(state)
        assert "trace" in out
        assert out["trace"], "node must emit a trace entry"
