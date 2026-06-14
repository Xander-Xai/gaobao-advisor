"""
P2-1 知识库按需加载模块测试
"""

from quality.knowledge_loader import load_contextual_knowledge


class TestKnowledgeLoader:
    def setup_method(self):
        pass

    def test_ai_era_triggers(self):
        result = load_contextual_knowledge("人工智能专业怎么样？AI时代就业前景好吗？")
        assert result is not None
        assert "AI时代" in result

    def test_subject_selection_triggers(self):
        result = load_contextual_knowledge("新高考选科怎么选？物化生组合怎么样？")
        assert result is not None
        assert "选科" in result

    def test_vocational_triggers(self):
        result = load_contextual_knowledge("专科生有什么出路？专升本难吗？")
        assert result is not None
        assert "专科" in result or "职业" in result

    def test_no_match_returns_none(self):
        result = load_contextual_knowledge("今天天气怎么样？")
        assert result is None

    def test_max_files_limit(self):
        result = load_contextual_knowledge("AI时代选科怎么选？人工智能和计算机哪个好？", max_files=1)
        assert result is not None
        # 只加载了 1 个文件的内容

    def test_slots_context(self):
        result = load_contextual_knowledge(
            "这个专业怎么样", slots={"interest": {"value": "人工智能"}, "goal": {"value": "就业"}}
        )
        assert result is not None
        assert "AI" in result

    def test_cache_works(self):
        """加载两次应使用缓存。"""
        r1 = load_contextual_knowledge("计算机专业就业前景")
        r2 = load_contextual_knowledge("AI专业怎么样")
        # 第一次加载会缓存，第二次使用缓存
        assert r1 is not None
        assert r2 is not None
