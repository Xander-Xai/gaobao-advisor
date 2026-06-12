"""
P2 新质量控制模块测试
- decision_framework: 8 条决策启发式
- anti_pattern_checker: 8 条反模式检测
- model_selector: 模型选择矩阵
"""
import pytest
from quality.decision_framework import (
    infer_scenario, recommend_heuristics, get_heuristic, list_heuristics,
)
from quality.anti_pattern_checker import (
    check_anti_patterns, should_rewrite, format_report,
)
from quality.model_selector import (
    infer_scenario as model_infer_scenario,
    infer_phase, select_models, format_model_hint,
)


# ── decision_framework ─────────────────────────────────────

class TestDecisionFramework:
    def test_list_heuristics_has_8(self):
        all_h = list_heuristics()
        assert len(all_h) == 8

    def test_infer_scenario_repeat_year(self):
        slots = {"goal": "复读", "interest": ""}
        assert infer_scenario(slots) == "repeat_year"

    def test_infer_scenario_grad_school(self):
        slots = {"goal": "考研", "interest": ""}
        assert infer_scenario(slots) == "grad_school"

    def test_infer_scenario_employment(self):
        slots = {"goal": "就业", "interest": ""}
        assert infer_scenario(slots) == "employment"

    def test_infer_scenario_default(self):
        slots = {}
        assert infer_scenario(slots) == "default"

    def test_recommend_includes_family_routing(self):
        """家庭分流是必选启发式。"""
        recs = recommend_heuristics({})
        keys = [r["key"] for r in recs]
        assert "family_routing" in keys

    def test_recommend_repeat_year_includes_ten_year_test(self):
        slots = {"goal": "复读"}
        recs = recommend_heuristics(slots, scenario="repeat_year")
        keys = [r["key"] for r in recs]
        assert "ten_year_test" in keys

    def test_get_heuristic_valid(self):
        h = get_heuristic("median_principle")
        assert h is not None
        assert h["name"] == "中位数原则"

    def test_get_heuristic_invalid(self):
        assert get_heuristic("nonexistent") is None


# ── anti_pattern_checker ────────────────────────────────────

class TestAntiPatternChecker:
    def test_no_anti_patterns(self):
        text = "你这情况很典型——湖北580分，普通家庭想靠技术吃饭。我建议你选计算机。"
        matches = check_anti_patterns(text, family_known=True)
        assert len(matches) == 0

    def test_rule1_vague_judgment(self):
        text = "这取决于你的个人情况，每个人情况不同。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 1 in ids

    def test_rule2_passion_without_family(self):
        text = "追随你的热爱，兴趣是最好的老师。"
        matches = check_anti_patterns(text, family_known=False)
        ids = [m.rule_id for m in matches]
        assert 2 in ids

    def test_rule2_passion_with_family_known(self):
        """已知家庭背景时，规则 2 不触发。"""
        text = "追随你的热爱，兴趣是最好的老师。"
        matches = check_anti_patterns(text, family_known=True)
        ids = [m.rule_id for m in matches]
        assert 2 not in ids

    def test_rule3_top_case(self):
        text = "计算机专业大厂年薪百万，进字节跳动轻松年入百万。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 3 in ids

    def test_rule4_academic_citation(self):
        text = "根据经济学原理，科斯定理告诉我们市场的力量。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 4 in ids

    def test_rule5_empty_talk(self):
        text = "AI时代就业前景很好，发展前景广阔光明。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 5 in ids

    def test_rule6_hedging_in_one_sentence(self):
        text = "这个问题可能或许需要综合考虑。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 6 in ids

    def test_rule8_academic_opening(self):
        text = "综上所述，这个专业值得报考。"
        matches = check_anti_patterns(text)
        ids = [m.rule_id for m in matches]
        assert 8 in ids

    def test_should_rewrite_error_threshold(self):
        from quality.anti_pattern_checker import AntiPatternMatch
        matches = [
            AntiPatternMatch(1, "模糊", "reason", "fix", severity="error"),
            AntiPatternMatch(6, "hedging", "reason", "fix", severity="warn"),
        ]
        assert should_rewrite(matches, error_threshold=1) is True

    def test_should_rewrite_false_for_warn_only(self):
        from quality.anti_pattern_checker import AntiPatternMatch
        matches = [
            AntiPatternMatch(6, "hedging", "reason", "fix", severity="warn"),
        ]
        assert should_rewrite(matches, error_threshold=1) is False

    def test_format_report_no_issues(self):
        assert "✅" in format_report([])


# ── model_selector ──────────────────────────────────────────

class TestModelSelector:
    def test_infer_scenario_normal_family(self):
        slots = {"family": "普通家庭", "goal": "就业"}
        assert model_infer_scenario(slots) == "普通家庭高考填志愿"

    def test_infer_scenario_rich_family(self):
        slots = {"family": "做生意"}
        assert model_infer_scenario(slots) == "富裕家庭高考填志愿"

    def test_infer_scenario_crisis(self):
        slots = {}
        assert model_infer_scenario(slots, "我崩溃了没希望了") == "情绪崩溃/高考失利"

    def test_infer_phase_no_score(self):
        slots = {}
        assert infer_phase(slots) == "探测期"

    def test_infer_phase_score_no_goal(self):
        slots = {"score": "580", "province": "湖北"}
        assert infer_phase(slots) == "定向期"

    def test_infer_phase_all_filled(self):
        slots = {"score": "580", "province": "湖北", "goal": "就业", "family": "普通家庭"}
        assert infer_phase(slots) == "精准推荐期"

    def test_select_models_normal(self):
        result = select_models({"family": "普通家庭", "goal": "就业"})
        assert "就业倒推法" in result["preferred"]
        assert "阶层现实主义" in result["preferred"]
        assert result["scenario"] == "普通家庭高考填志愿"

    def test_select_models_rich_family_bans_class_real(self):
        result = select_models({"family": "做生意", "score": "600", "province": "北京", "goal": "就业"})
        assert "阶层现实主义" in result["banned"]

    def test_select_models_crisis_bans_controversy(self):
        result = select_models({}, user_input="我崩溃了没希望了")
        assert "争议即传播" in result["banned"]

    def test_format_model_hint(self):
        result = select_models({"family": "普通家庭", "goal": "就业"})
        hint = format_model_hint(result)
        assert "普通家庭" in hint
        assert "就业倒推法" in hint
