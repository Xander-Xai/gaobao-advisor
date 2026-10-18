"""Tests for the structured-query node's slot normalisation."""

from __future__ import annotations

from server.graph.nodes.data_nodes import data_query_node, numeric_score


class TestNumericScore:
    def test_reads_plain_score(self) -> None:
        assert numeric_score({"score": 580}) == 580

    def test_reads_extracted_score_rank(self) -> None:
        assert numeric_score({"score_rank": "600分"}) == 600

    def test_reads_score_when_rank_is_also_present(self) -> None:
        assert numeric_score({"score_rank": "600分 / 位次3000"}) == 600

    def test_does_not_treat_rank_only_as_score(self) -> None:
        assert numeric_score({"score_rank": "位次3000"}) is None

    def test_rejects_out_of_range(self) -> None:
        assert numeric_score({"score_rank": "99分"}) is None
        assert numeric_score({"score_rank": "900分"}) is None


class TestDataQueryNode:
    def test_uses_extracted_score_in_structured_query(self, monkeypatch) -> None:
        from server.graph.nodes import data_nodes

        calls: dict[str, object] = {}

        class _FakeDataQuery:
            @staticmethod
            def query_match_schools_v2(**kwargs):
                calls["match"] = kwargs
                return [{"school_name": "示例大学（合成）"}]

            @staticmethod
            def query_yi_fen_yi_duan(province, score, subject_type):
                calls["rank"] = (province, score, subject_type)
                return {"rank": 123, "score": score}

            @staticmethod
            def query_schools_by_major(**kwargs):
                calls["major"] = kwargs
                return {"total": 1}

            @staticmethod
            def query_major_info(name):
                return None

        monkeypatch.setattr(data_nodes, "dq", _FakeDataQuery)

        result = data_query_node(
            {
                "scene": "gaokao",
                "slots": {
                    "province": "示例省·甲",
                    "score_rank": "600分",
                    "subject": "物理",
                    "interest": "计算机",
                },
            }
        )

        assert calls["match"]["score"] == 600
        assert calls["rank"] == ("示例省·甲", 600, "物理")
        assert result["data_query_results"]["match_schools"]
        assert result["data_query_results"]["rank_info"]["rank"] == 123


class TestSlotExtractDerivesScore:
    def test_extracts_demo_slots_and_numeric_score(self) -> None:
        from server.graph.nodes.extract import slot_extract_node

        out = slot_extract_node(
            {
                "input_text": "我是示例省·甲的物理类考生，600分，想报计算机",
                "slots": {},
            }
        )

        assert out["slots"]["province"] == "示例省·甲"
        assert out["slots"]["score_rank"] == "600分"
        assert out["slots"]["score"] == 600
        assert out["slots"]["interest"] == "计算机"
