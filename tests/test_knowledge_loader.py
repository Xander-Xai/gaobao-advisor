"""knowledge_loader 模块测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quality.knowledge_loader import load_contextual_knowledge


class TestKnowledgeLoader:
    def test_returns_none_for_no_match(self):
        result = load_contextual_knowledge("今天天气真好", {})
        assert result is None

    def test_kb_retriever_none_uses_old_system(self):
        result = load_contextual_knowledge("AI要替代人类了", {}, kb_retriever=None)
        assert result is None or isinstance(result, str)

    def test_kb_retriever_used_when_provided(self):
        class MockChunk:
            def __init__(self, text):
                self.text = text

        class MockResult:
            group_chunks = [MockChunk("mock content")]

        class MockRetriever:
            def search(self, msg, slots):
                return MockResult()

        result = load_contextual_knowledge("测试查询", {}, kb_retriever=MockRetriever())
        assert result == "mock content"
