"""Tests for service wrappers — verify they import and expose correct interfaces."""


class TestEmotionWrapper:
    """Tests for the emotion service wrapper."""

    def test_detect_emotion_returns_expected_keys(self):
        from server.services.emotion import detect_emotion

        result = detect_emotion("我好焦虑，不知道该怎么办")
        assert "level" in result
        assert "score" in result
        assert "strategy" in result
        assert "matched_keywords" in result
        assert "hint" in result

    def test_detect_emotion_anxiety(self):
        from server.services.emotion import detect_emotion

        result = detect_emotion("我好焦虑，不知道该怎么办")
        assert result["level"] == "\U0001f7e1"  # yellow
        assert result["strategy"] == "empathize_first"

    def test_detect_emotion_crisis(self):
        from server.services.emotion import detect_emotion

        result = detect_emotion("我崩溃了，想死，不想活了")
        assert result["level"] == "\U0001f534"  # red
        assert result["strategy"] == "crisis"

    def test_detect_emotion_normal(self):
        from server.services.emotion import detect_emotion

        result = detect_emotion("请问北京有哪些好大学？")
        assert result["level"] == "\U0001f7e2"  # green
        assert result["strategy"] == "standard"

    def test_detect_emotion_empty(self):
        from server.services.emotion import detect_emotion

        result = detect_emotion("")
        assert result["score"] == 0

    def test_get_crisis_hotlines(self):
        from server.services.emotion import get_crisis_hotlines

        hotlines = get_crisis_hotlines()
        assert isinstance(hotlines, list)
        assert len(hotlines) > 0


class TestDataQueryWrapper:
    """Tests for the data_query service wrapper (interface existence)."""

    def test_import_all_functions(self):
        from server.services import data_query

        assert callable(data_query.query_admission)
        assert callable(data_query.query_enrollment_plan)
        assert callable(data_query.query_yi_fen_yi_duan)
        assert callable(data_query.query_match_schools_v2)
        assert callable(data_query.query_match_schools)
        assert callable(data_query.query_schools_by_major)
        assert callable(data_query.query_school_info)
        assert callable(data_query.query_major_info)
        assert callable(data_query.query_subject_ranking)
        assert callable(data_query.search_policy)
        assert callable(data_query.get_db_stats)
        assert callable(data_query.check_user_subject_compatibility)
        assert callable(data_query.generate_volunteer_table)
        assert callable(data_query.query_admission_trend)

    def test_search_policy_works(self):
        """search_policy uses the in-memory POLICIES dict, no DB needed."""
        from server.services.data_query import search_policy

        results = search_policy("强基计划")
        assert isinstance(results, list)
        assert len(results) > 0
        assert results[0]["title"] == "强基计划"

    def test_get_db_stats_returns_dict(self):
        """get_db_stats should return a dict (may say DB unavailable)."""
        from server.services.data_query import get_db_stats

        stats = get_db_stats()
        assert isinstance(stats, dict)


class TestRagWrapper:
    """Tests for the RAG service wrapper (interface existence)."""

    def test_import_functions(self):
        from server.services import rag

        assert callable(rag.search)
        assert callable(rag.load_contextual_knowledge)
        assert callable(rag.configure)

    def test_configure_sets_paths(self):
        from server.services import rag

        # Should not raise
        rag.configure("/tmp/fake_groups", "/tmp/fake_quotes")


class TestQualityOrchestrator:
    """Tests for the quality orchestrator."""

    def test_instantiation(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        # Access lazy properties — they should not raise
        assert orch.model_selector is not None
        assert orch.decision_framework is not None

    def test_all_lazy_properties(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        # All 7 modules should be accessible
        assert orch.model_selector is not None
        assert orch.decision_framework is not None
        assert orch.anti_pattern_checker is not None
        assert orch.emotion_detector is not None
        assert orch.ai_era_risk is not None
        assert orch.cross_validator is not None
        assert orch.knowledge_loader is not None

    def test_detect_emotion_delegates(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.detect_emotion("我好焦虑，不知道该怎么办")
        assert "level" in result
        assert result["strategy"] == "empathize_first"

    def test_select_models_delegates(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.select_models(
            {"province": "北京", "score": 620, "goal": "就业"},
            "我想报计算机专业",
        )
        assert "scenario" in result
        assert "preferred" in result
        assert "banned" in result

    def test_recommend_heuristics_delegates(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.recommend_heuristics({"province": "北京", "score": 620})
        assert isinstance(result, list)
        assert len(result) > 0
        # Default heuristics should always include soul_interrogation
        keys = [h["key"] for h in result]
        assert "soul_interrogation" in keys

    def test_check_anti_patterns_delegates(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        # Text with known anti-patterns
        result = orch.check_anti_patterns("这取决于你自己的选择，因人而异。建议你综合考虑多方面因素。")
        assert isinstance(result, list)
        assert len(result) > 0
        assert any(m["rule_id"] == 1 for m in result)

    def test_get_major_risk(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        # May return None if the JSON file is empty or missing
        result = orch.get_major_risk("计算机科学与技术")
        # Just verify it doesn't raise
        assert result is None or isinstance(result, dict)

    def test_cross_validate(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        sources = [
            {"source": "T1", "min_score": 620, "min_rank": 5000},
            {"source": "T2", "min_score": 618, "min_rank": 5200},
        ]
        result = orch.cross_validate(sources)
        assert result is not None
        assert result["confidence"] in ("高", "中", "低")

    def test_run_pre_generation_checks(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.run_pre_generation_checks(
            "我好焦虑，不知道该怎么办",
            {"province": "北京", "score": 620},
        )
        assert "emotion" in result
        assert "model_selection" in result
        assert "heuristics" in result

    def test_run_post_generation_checks_clean(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.run_post_generation_checks("我跟你说，根据你的620分和北京户口，我建议你重点关注计算机专业。")
        assert "anti_patterns" in result
        assert "should_rewrite" in result
        assert result["should_rewrite"] is False

    def test_run_post_generation_checks_dirty(self):
        from server.services.quality import QualityOrchestrator

        orch = QualityOrchestrator()
        result = orch.run_post_generation_checks("这取决于你自己的选择，因人而异。建议你综合考虑多方面因素。")
        assert result["should_rewrite"] is True
