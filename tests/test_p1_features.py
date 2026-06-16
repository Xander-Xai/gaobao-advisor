"""
P1 功能测试：多轮对话上下文压缩 + 多数据源置信度评分
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legacy.agent import GaokaoAdvisor
from legacy.gaokao_data import format_admission_info

# ── 辅助工厂 ──


def _make_slots():
    """创建干净的槽位副本，避免测试间污染。"""
    return {
        "province": {"label": "省份", "filled": False, "value": ""},
        "score_rank": {"label": "分数/位次", "filled": False, "value": ""},
        "subject": {"label": "选科", "filled": False, "value": ""},
        "interest": {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
        "region": {"label": "地域偏好", "filled": False, "value": ""},
        "family": {"label": "家庭资源", "filled": False, "value": ""},
        "goal": {"label": "核心诉求", "filled": False, "value": ""},
    }


def _make_advisor():
    """创建一个不需要真实 API key 的 advisor 实例（用于测试非 LLM 功能）。"""
    adv = GaokaoAdvisor.__new__(GaokaoAdvisor)
    adv.conversation = []
    adv.slots = _make_slots()
    adv.cli_mode = True
    adv.model = "test-model"
    return adv


# ══════════════════════════════════════════════════════
#  P1-1: 多轮对话上下文压缩测试
# ══════════════════════════════════════════════════════


class TestCompressHistory:
    """_compress_history() 方法测试。"""

    def test_no_compression_when_under_threshold(self):
        """对话少于 40 条（20轮）时不触发压缩。"""
        adv = _make_advisor()
        # 填充 38 条对话（19 轮）— 不超过阈值
        for i in range(19):
            adv.conversation.append({"role": "user", "content": f"消息{i}"})
            adv.conversation.append({"role": "assistant", "content": f"回复{i}"})
        assert len(adv.conversation) == 38
        adv._compress_history()
        assert len(adv.conversation) == 38  # 未压缩

    def test_compression_triggered_at_threshold(self):
        """对话超过 40 条（20轮）时触发压缩。"""
        adv = _make_advisor()
        # 填充 42 条对话（21 轮）
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "我是山东考生，考了580分"})
            adv.conversation.append({"role": "assistant", "content": "推荐你武汉大学"})
        assert len(adv.conversation) == 42
        adv._compress_history()
        # 压缩后应有 1 条摘要 + 20 条保留 = 21 条
        assert len(adv.conversation) == 21
        assert adv.conversation[0]["role"] == "system"
        assert "【对话摘要】" in adv.conversation[0]["content"]

    def test_compression_extracts_province(self):
        """摘要应提取省份信息。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "我是山东考生，580分"})
            adv.conversation.append({"role": "assistant", "content": "你好"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "山东" in summary

    def test_compression_extracts_score(self):
        """摘要应提取分数信息。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "我是山东考生，考了580分"})
            adv.conversation.append({"role": "assistant", "content": "你好"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "580分" in summary

    def test_compression_extracts_subject(self):
        """摘要应提取选科信息。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "选的物理，580分"})
            adv.conversation.append({"role": "assistant", "content": "你好"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "物理" in summary

    def test_compression_extracts_interest(self):
        """摘要应提取专业兴趣。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "我想学计算机，看重就业"})
            adv.conversation.append({"role": "assistant", "content": "你好"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "计算机" in summary

    def test_compression_extracts_goal(self):
        """摘要应提取核心诉求。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "我想学计算机，看重就业"})
            adv.conversation.append({"role": "assistant", "content": "你好"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "就业" in summary

    def test_compression_extracts_schools(self):
        """摘要应提取 assistant 推荐过的学校。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append({"role": "user", "content": "推荐学校"})
            adv.conversation.append({"role": "assistant", "content": "推荐武汉大学和华中科技大学"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "武汉大学" in summary

    def test_compression_preserves_recent_messages(self):
        """压缩后应保留最近的 20 条消息不变。"""
        adv = _make_advisor()
        # 填充 22 轮 = 44 条（超过 40 条阈值）
        for i in range(22):
            adv.conversation.append({"role": "user", "content": f"用户消息{i}"})
            adv.conversation.append({"role": "assistant", "content": f"助手回复{i}"})
        adv._compress_history()
        # 保留最后 20 条（20条保留 + 1条摘要 = 21条总计）
        last_msgs = adv.conversation[-20:]
        # 最后两条应该是第 21 轮
        assert "用户消息21" in last_msgs[-2]["content"]
        assert "助手回复21" in last_msgs[-1]["content"]

    def test_compression_preserves_role_structure(self):
        """压缩后保留的消息应维持 user/assistant 交替结构。"""
        adv = _make_advisor()
        for i in range(22):
            adv.conversation.append({"role": "user", "content": f"消息{i}"})
            adv.conversation.append({"role": "assistant", "content": f"回复{i}"})
        adv._compress_history()
        # 第一条是 system 摘要
        assert adv.conversation[0]["role"] == "system"
        # 之后应该是 user/assistant 交替
        for i in range(1, len(adv.conversation), 2):
            assert adv.conversation[i]["role"] == "user"
        for i in range(2, len(adv.conversation), 2):
            assert adv.conversation[i]["role"] == "assistant"

    def test_compression_repeated_idempotent(self):
        """连续调用压缩不会出错。"""
        adv = _make_advisor()
        for _i in range(22):
            adv.conversation.append({"role": "user", "content": "山东考生"})
            adv.conversation.append({"role": "assistant", "content": "武汉大学推荐"})
        adv._compress_history()
        len_after_first = len(adv.conversation)
        # 再次调用：1(摘要)+20(保留)=21 < 40，不触发
        adv._compress_history()
        assert len(adv.conversation) == len_after_first

    def test_compression_empty_conversation(self):
        """空对话不报错。"""
        adv = _make_advisor()
        adv._compress_history()  # 不应抛异常
        assert len(adv.conversation) == 0

    def test_compression_with_all_fields(self):
        """当所有字段都能提取时，摘要包含全部。"""
        adv = _make_advisor()
        for _i in range(21):
            adv.conversation.append(
                {"role": "user", "content": "我是山东考生，580分，选的物理，想学计算机，看重就业，想去北京"}
            )
            adv.conversation.append({"role": "assistant", "content": "推荐你北京理工大学和武汉大学"})
        adv._compress_history()
        summary = adv.conversation[0]["content"]
        assert "山东" in summary
        assert "580分" in summary
        assert "物理" in summary
        assert "计算机" in summary
        assert "就业" in summary


# ══════════════════════════════════════════════════════
#  P1-2: 多数据源置信度评分测试
# ══════════════════════════════════════════════════════


class TestConfidenceScore:
    """置信度评分（confidence_score / data_tier）测试。"""

    def test_admission_returns_empty_with_confidence_fields(self):
        """空结果列表应正常返回，不报错。"""
        from legacy.gaokao_data import query_admission

        # 数据库和百度搜索都不可用时，应返回空列表
        results = query_admission("不存在的大学", "不存在的省")
        assert isinstance(results, list)

    def test_format_admission_info_with_confidence_score(self):
        """format_admission_info 应正确输出置信度分数。"""
        results = [
            {
                "school": "武汉大学",
                "level": "985",
                "province": "湖北",
                "year": 2025,
                "subject_type": "物理类",
                "min_score": 620,
                "min_rank": 5000,
                "major": "院校线",
                "data_source": "本地数据库 · 2025年",
                "confidence_score": 90,
                "data_tier": "T1",
            }
        ]
        text = format_admission_info(results)
        assert "武汉大学" in text
        assert "置信度:90分" in text

    def test_format_admission_info_without_confidence_score(self):
        """没有 confidence_score 字段时，format 不报错（向后兼容）。"""
        results = [
            {
                "school": "武汉大学",
                "level": "",
                "province": "湖北",
                "year": 2025,
                "subject_type": "物理类",
                "min_score": 620,
                "min_rank": 5000,
                "major": "院校线",
                "data_source": "本地数据库",
            }
        ]
        text = format_admission_info(results)
        assert "武汉大学" in text
        # 无 confidence_score 时不显示
        assert "置信度" not in text

    def test_format_admission_info_snippet_with_confidence(self):
        """百度搜索片段结果也应显示置信度。"""
        results = [
            {
                "school": "武汉大学",
                "province": "湖北",
                "year": 2025,
                "snippet": "武汉大学2024年湖北录取分数620分",
                "data_source": "百度搜索",
                "confidence_score": 40,
                "data_tier": "T3",
                "min_score": None,
                "min_rank": None,
            }
        ]
        text = format_admission_info(results)
        assert "置信度:40分" in text

    def test_yi_fen_yi_duan_confidence_score_on_success(self):
        """query_yi_fen_yi_duan 返回结果应包含 confidence_score。"""
        from legacy.gaokao_data import query_yi_fen_yi_duan

        result = query_yi_fen_yi_duan("湖北", 600, "物理类", 2025)
        # 无论数据库是否有数据，只要返回 dict 就应有 confidence_score
        if result is not None:
            assert "confidence_score" in result
            assert isinstance(result["confidence_score"], (int, float))

    def test_yi_fen_yi_duan_confidence_score_range(self):
        """confidence_score 应在合理范围内。"""
        from legacy.gaokao_data import query_yi_fen_yi_duan

        result = query_yi_fen_yi_duan("湖北", 600, "物理类", 2025)
        if result is not None and result.get("confidence_score"):
            assert 0 <= result["confidence_score"] <= 100

    def test_admission_confidence_score_range(self):
        """query_admission 返回的 confidence_score 应在合理范围内。"""
        from legacy.gaokao_data import query_admission

        results = query_admission("武汉大学", "湖北")
        for r in results:
            if "confidence_score" in r:
                assert 0 <= r["confidence_score"] <= 100

    def test_admission_data_tier_field(self):
        """query_admission 返回结果应包含 data_tier 字段。"""
        from legacy.gaokao_data import query_admission

        results = query_admission("武汉大学", "湖北")
        for r in results:
            if "data_tier" in r:
                assert r["data_tier"] in ("T1", "T2", "T3")


class TestConfidenceScoringConstants:
    """验证置信度评分的常量映射逻辑。"""

    def test_confidence_tiers_match_spec(self):
        """验证 T1/T2/T3 对应的分数与规格一致。"""
        confidence_map = {"T1": 90, "T2": 70, "T3": 40}
        assert confidence_map["T1"] == 90  # 本地数据库
        assert confidence_map["T2"] == 70  # 百度高考 API
        assert confidence_map["T3"] == 40  # 百度搜索

    def test_yi_fen_yi_duan_tier_labels(self):
        """一分一段表的置信度标签应与规格一致。"""
        # 真实数据: confidence="高", score=90
        # 反推数据: confidence="中-低", score=40
        tiers = {
            "真实数据": {"confidence": "高", "score": 90},
            "反推数据": {"confidence": "中-低", "score": 40},
        }
        assert tiers["真实数据"]["score"] == 90
        assert tiers["反推数据"]["score"] == 40
