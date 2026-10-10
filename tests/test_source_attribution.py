"""数据来源标注硬规则后处理测试。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.graph.nodes.source_attribution import validate_source_attribution


class TestScoreAnnotation:
    """分数/位次标注测试。"""

    def test_score_without_source_annotated(self) -> None:
        """含分数的句子无来源时应被标注。"""
        reply = "你的分数是 580 分,可以去武汉理工大学。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" in result
        assert "580" in result

    def test_score_with_source_unchanged(self) -> None:
        """已带来源的句子不应被重复标注。"""
        reply = "580 分（来源：湖北省考试院 2024 年）"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result
        assert result == reply

    def test_vague_data_claim_is_not_treated_as_a_source(self) -> None:
        reply = "数据显示，该校录取线为 580 分。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" in result

    def test_source_without_year_is_marked_incomplete(self) -> None:
        reply = "该校录取线为 580 分（来源：省教育考试院）。"
        result = validate_source_attribution(reply)
        assert "来源年份待补全" in result

    def test_rank_with_source_unchanged(self) -> None:
        """位次 + 来源不应被标。"""
        reply = "你的全省位次为 2 万名（来源：湖北省一分一段表 2024）"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result


class TestSalaryAnnotation:
    """薪资数据标注测试。"""

    def test_salary_without_source(self) -> None:
        """薪资数字无来源应被标注。"""
        reply = "这个专业毕业 5 年后年薪 30 万。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" in result

    def test_salary_with_source(self) -> None:
        """带来源的薪资不应被标。"""
        reply = "年薪 30 万（来源：XX 大学 2024 年就业质量报告）"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_salary_range(self) -> None:
        """薪资区间也应被标注。"""
        reply = "该专业起薪 8-15 万。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" in result


class TestEmploymentRate:
    """就业率标注测试。"""

    def test_employment_rate(self) -> None:
        """就业率无来源应被标注。"""
        reply = "本专业就业率 95%。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" in result

    def test_employment_rate_with_source(self) -> None:
        """带来源的就业率不应被标。"""
        reply = "就业率 95%（来源：教育部 2024 年高校就业统计）"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result


class TestSafeNumbers:
    """安全数字测试（不应被标）。"""

    def test_ordinal_numbers_unchanged(self) -> None:
        """句首"第N"格式不变。"""
        reply = "第一,要看你的兴趣。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_year_unchanged(self) -> None:
        """年份不应被标。"""
        reply = "2024 年高考报名人数创新高。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_list_numbering_unchanged(self) -> None:
        """列表序号不应被标。"""
        reply = "1、首先看分数。2、其次看专业。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_month_unchanged(self) -> None:
        """月份不应被标。"""
        reply = "6 月高考,7 月出分。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result


class TestDisclaimersPreserved:
    """免责声明应保持完整。"""

    def test_disclaimer_unchanged(self) -> None:
        """免责声明不应被改写。"""
        reply = "声明：以上分析基于公开数据和 AI 模型,仅供参考。"
        result = validate_source_attribution(reply)
        assert result == reply
        assert "数据来源待补全" not in result

    def test_separator_unchanged(self) -> None:
        """分隔线不应被改写。"""
        reply = "---"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result


class TestSentenceBoundary:
    """句子边界处理测试。"""

    def test_multi_sentence_preserves_structure(self) -> None:
        """多句子结构应被正确处理。"""
        reply = "你的分数是 580 分,可以去武汉理工大学。你的录取线参考是 590 分。"
        result = validate_source_attribution(reply)
        # 两句都含分数+分，都应被标
        assert result.count("数据来源待补全") >= 2
        # 句末不应出现双句号
        assert "。。" not in result

    def test_multi_sentence_with_safe_number(self) -> None:
        """含安全数字的句子不应被标。"""
        reply = "你的分数是 580 分,可以去武汉理工大学。武汉理工是 211。"
        result = validate_source_attribution(reply)
        # 580分应被标, 211不应被标（211是"211工程"标识，不是数据）
        assert result.count("数据来源待补全") == 1
        assert "。。" not in result

    def test_empty_string_returns_empty(self) -> None:
        """空字符串应原样返回。"""
        assert validate_source_attribution("") == ""

    def test_no_numbers_unchanged(self) -> None:
        """无数字的句子不应被改写。"""
        reply = "我先了解你的情况。"
        result = validate_source_attribution(reply)
        assert result == reply


class TestEducationBadgeSafe:
    """教育标识(985/211)豁免测试 — 这些是学校类型标识而非数据。"""

    def test_985_yuanxiao_not_annotated(self) -> None:
        """'985 院校' 不应被标(教育标识+学校类别)。"""
        reply = "985 院校有 39 所。"
        result = validate_source_attribution(reply)
        # "所"已从单位列表中移除,所以不会被匹配
        assert "数据来源待补全" not in result

    def test_211_zhuan_dotted_not_annotated(self) -> None:
        """'211' 标识后跟名词不应被标。"""
        reply = "211 院校有 116 所。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_shuangyiliu_not_annotated(self) -> None:
        """'双一流' 不应被误标。"""
        reply = "双一流 院校有哪些?"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result

    def test_365_days_not_annotated(self) -> None:
        """'365 天' 不应被误标(天不在单位列表中)。"""
        reply = "一年有 365 天。"
        result = validate_source_attribution(reply)
        assert "数据来源待补全" not in result


class TestExceptionSafety:
    """异常保护测试。"""

    def test_render_node_does_not_crash_on_emoji(self) -> None:
        """render 节点不应因特殊字符崩溃。"""
        from server.graph.nodes.render import render_reply_node

        state = {
            "reply": "你的分数是 580 分,可以上武汉理工。🎉",
            "trace": [],
        }
        result = render_reply_node(state)
        assert "reply" in result
        assert "声明" in result["reply"]

    def test_render_node_with_empty_state(self) -> None:
        """空状态应不崩。"""
        from server.graph.nodes.render import render_reply_node

        result = render_reply_node({})
        assert "reply" in result
        assert "声明" in result["reply"]


class TestSourceAttributionNode:
    """source_attribution_node (graph node) 集成测试。"""

    def test_source_attribution_node_annotates_unattributed(self) -> None:
        """确认 source_attribution_node 标注无来源数据。"""
        from server.graph.nodes.source_attribution import source_attribution_node

        # 模拟一个 LLM 已生成 reply 的状态
        state = {
            "reply": "你的分数是 580 分,可以上武汉理工。",
            "trace": [],
        }
        result = source_attribution_node(state)
        assert "数据来源待补全" in result["reply"]
        assert "source_attribution_done" in [t["event"] for t in result["trace"]]

    def test_source_attribution_node_no_extra_annotation(self) -> None:
        """带来源的回复不应被重复标注。"""
        from server.graph.nodes.source_attribution import source_attribution_node

        state = {
            "reply": "580 分（来源：湖北省考试院 2024 年）",
            "trace": [],
        }
        result = source_attribution_node(state)
        assert result["reply"].count("数据来源待补全") == 0
