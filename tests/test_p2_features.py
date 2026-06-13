"""
P2 功能测试 — 3+3 省份专项适配 / 方言友好

覆盖：
  - 3+3 省份选科组合识别（20种 + 自然表达）
  - 方言省份推测
  - 口语化分数表达（五百八、差一本线N分、不到600）
  - 方言情绪检测
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import (
    PROVINCES_33,
    SUBJECT_COMBOS_33,
    _expand_subject_combo,
    _parse_oral_score,
    extract_slots_from_message,
)

# ── 辅助工厂 ──

def _make_slots():
    """创建干净的槽位副本，避免测试间污染。"""
    return {
        "province":     {"label": "省份", "filled": False, "value": ""},
        "score_rank":   {"label": "分数/位次", "filled": False, "value": ""},
        "subject":      {"label": "选科", "filled": False, "value": ""},
        "interest":     {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
        "region":       {"label": "地域偏好", "filled": False, "value": ""},
        "family":       {"label": "家庭资源", "filled": False, "value": ""},
        "goal":         {"label": "核心诉求", "filled": False, "value": ""},
    }


# ══════════════════════════════════════════════════════
#  P2-2: 3+3 省份专项适配
# ══════════════════════════════════════════════════════

class Test33ProvinceSubjectCombos:
    """3+3 省份选科组合识别（20种组合 + 单科）"""

    def test_expand_subject_combo_basic(self):
        """物化生 → 物理+化学+生物"""
        assert _expand_subject_combo("物化生") == "物理+化学+生物"

    def test_expand_subject_combo_politics(self):
        """物化政 → 物理+化学+政治"""
        assert _expand_subject_combo("物化政") == "物理+化学+政治"

    def test_expand_subject_combo_history(self):
        """政地史 → 政治+地理+历史"""
        assert _expand_subject_combo("政地史") == "政治+地理+历史"

    def test_all_33_combos_expandable(self):
        """所有 20 种 3+3 组合都能展开为 3 个科目"""
        for combo in SUBJECT_COMBOS_33:
            expanded = _expand_subject_combo(combo)
            parts = expanded.split("+")
            assert len(parts) == 3, f"组合 {combo} 展开后不是3个科目: {expanded}"
            for part in parts:
                assert part in ["物理", "化学", "生物", "历史", "地理", "政治"], \
                    f"展开后的科目名不合法: {part}"

    def test_33_combo_count(self):
        """确认 3+3 有 20 种组合"""
        assert len(SUBJECT_COMBOS_33) == 20

    @pytest.mark.parametrize("combo", [
        "物化生", "物化政", "物化地", "物生政", "物生地", "物政地",
        "化生政", "化生地", "化政地", "生政地",
    ])
    def test_33_combo_slot_extraction(self, combo):
        """3+3 组合能被 extract_slots_from_message 识别"""
        s = _make_slots()
        extract_slots_from_message(f"我是浙江考生，选的{combo}", s)
        assert s["subject"]["filled"] is True
        assert s["subject"]["value"] == combo

    def test_33_natural_expression_three_subjects(self):
        """'选了物理化学地理' → 物理+化学+地理"""
        s = _make_slots()
        extract_slots_from_message("选了物理化学地理", s)
        assert s["subject"]["filled"] is True
        assert "物理" in s["subject"]["value"]
        assert "化学" in s["subject"]["value"]
        assert "地理" in s["subject"]["value"]

    def test_33_natural_expression_with_xuankao(self):
        """'选考政治历史生物' → 政治+历史+生物"""
        s = _make_slots()
        extract_slots_from_message("选考政治历史生物", s)
        assert s["subject"]["filled"] is True
        assert "政治" in s["subject"]["value"]
        assert "历史" in s["subject"]["value"]
        assert "生物" in s["subject"]["value"]

    def test_33_provinces_set(self):
        """确认 6 个 3+3 省份"""
        assert PROVINCES_33 == {"浙江", "上海", "北京", "天津", "山东", "海南"}

    def test_33_single_subject_physics(self):
        """3+3 省份单科选物理"""
        s = _make_slots()
        extract_slots_from_message("我是浙江考生选的物理", s)
        assert s["subject"]["value"] == "物理"

    def test_33_single_subject_chemistry(self):
        """3+3 省份单科选化学（之前只支持物理/历史裸关键词）"""
        s = _make_slots()
        extract_slots_from_message("我是北京考生，选的化学", s)
        assert s["subject"]["filled"] is True
        assert "化学" in s["subject"]["value"]

    def test_33_politics_geography_history_combo(self):
        """'政史地' 是传统文科组合，3+3 中也可选"""
        s = _make_slots()
        extract_slots_from_message("政史地组合", s)
        assert s["subject"]["filled"] is True
        assert s["subject"]["value"] == "政史地"


# ══════════════════════════════════════════════════════
#  P2-5: 方言友好
# ══════════════════════════════════════════════════════

class TestDialectProvinceDetection:
    """方言→省份推测"""

    def test_dialect_shandong(self):
        """'俺' → 山东（默认取候选列表第一个）"""
        s = _make_slots()
        extract_slots_from_message("俺考了580分，想学计算机", s)
        assert s["province"]["filled"] is True
        assert s["province"]["value"] == "山东"

    def test_dialect_shanghai(self):
        """'阿拉' → 上海"""
        s = _make_slots()
        extract_slots_from_message("阿拉考了560分", s)
        assert s["province"]["filled"] is True
        assert s["province"]["value"] == "上海"

    def test_dialect_shaanxi(self):
        """'额' → 陕西"""
        s = _make_slots()
        extract_slots_from_message("额考了510分", s)
        assert s["province"]["filled"] is True
        assert s["province"]["value"] == "陕西"

    def test_dialect_not_override_explicit(self):
        """方言不应覆盖已明确提到的省份"""
        s = _make_slots()
        extract_slots_from_message("我是河南人，俺考了580分", s)
        assert s["province"]["value"] == "河南"


class TestOralScoreDetection:
    """口语化分数表达"""

    def test_oral_score_wu_ba(self):
        """'五百八' → 580"""
        assert _parse_oral_score("五百八") == 580

    def test_oral_score_liu_bai(self):
        """'六百' → 600"""
        assert _parse_oral_score("六百") == 600

    def test_oral_score_in_message(self):
        """'考了五百八' → 580分"""
        s = _make_slots()
        extract_slots_from_message("考了五百八", s)
        assert s["score_rank"]["filled"] is True
        assert "580" in s["score_rank"]["value"]

    def test_oral_score_chu_tou(self):
        """'六百出头' → 600"""
        s = _make_slots()
        extract_slots_from_message("六百出头", s)
        # 应该被解析为 >= 600
        assert s["score_rank"]["filled"] is True

    def test_delta_score_below_yi_ben(self):
        """'差一本线20分' → 低于一本线20分"""
        s = _make_slots()
        extract_slots_from_message("差一本线20分", s)
        assert s["score_rank"]["filled"] is True
        assert "低于一本线20分" == s["score_rank"]["value"]

    def test_delta_score_above_ben_ke(self):
        """'过了本科线30分' → 高于一本线30分"""
        s = _make_slots()
        extract_slots_from_message("过了本科线30分", s)
        assert s["score_rank"]["filled"] is True
        assert "高于一本线" in s["score_rank"]["value"]

    def test_delta_score_bu_dao(self):
        """'不到600' → <600分"""
        s = _make_slots()
        extract_slots_from_message("不到600", s)
        assert s["score_rank"]["filled"] is True
        assert "<600" in s["score_rank"]["value"]

    def test_delta_score_mei_dao(self):
        """'没到600' → <600分"""
        s = _make_slots()
        extract_slots_from_message("没到600", s)
        assert s["score_rank"]["filled"] is True
        assert "<600" in s["score_rank"]["value"]


class TestDialectEmotionDetection:
    """方言情绪检测"""

    def test_wan_du_zi(self):
        """'完犊子了' → 焦虑"""
        from quality.emotion_detector import detect_emotion
        result = detect_emotion("完犊子了，这次考砸了")
        assert result["score"] > 0
        assert "完犊子了" in result["matched_keywords"]

    def test_zheng_bu_hui(self):
        """'整不会了' → 迷茫"""
        from quality.emotion_detector import detect_emotion
        result = detect_emotion("整不会了，不知道咋选")
        assert result["score"] > 0
        assert "整不会了" in result["matched_keywords"]

    def test_ke_za_zheng(self):
        """'可咋整' → 焦虑"""
        from quality.emotion_detector import detect_emotion
        result = detect_emotion("可咋整啊，志愿还没填")
        assert result["score"] > 0
        assert "可咋整" in result["matched_keywords"]

    def test_chou_si_le(self):
        """'愁死了' → 焦虑"""
        from quality.emotion_detector import detect_emotion
        result = detect_emotion("愁死了，选啥专业好")
        assert result["score"] > 0
        assert "愁死了" in result["matched_keywords"]

    def test_mei_zi_zi(self):
        """'美滋滋' → 积极（被识别为关键词）"""
        from quality.emotion_detector import detect_emotion
        result = detect_emotion("美滋滋，考了650分")
        assert "美滋滋" in result["matched_keywords"]


# ══════════════════════════════════════════════════════
#  综合集成测试
# ══════════════════════════════════════════════════════

class TestIntegration:
    """综合集成：方言 + 3+3 + 口语分数同时出现"""

    def test_shandong_dialect_with_oral_score(self):
        """山东方言 + 口语分数 + 诉求"""
        s = _make_slots()
        extract_slots_from_message("俺考了五百八，想学计算机，看重就业", s)
        assert s["province"]["value"] == "山东"
        assert "580" in s["score_rank"]["value"]
        assert "计算机" in s["interest"]["value"]
        assert s["goal"]["value"] == "就业"

    def test_shanghai_33_with_combo(self):
        """上海考生 + 3+3 选科组合"""
        s = _make_slots()
        extract_slots_from_message("阿拉是上海考生，选了物化生", s)
        assert s["province"]["value"] == "上海"
        assert s["subject"]["value"] == "物化生"

    def test_zhejiang_33_natural_subjects(self):
        """浙江考生 + 自然表达选科"""
        s = _make_slots()
        extract_slots_from_message("我是浙江考生，选了物理化学地理", s)
        assert s["province"]["value"] == "浙江"
        assert "物理" in s["subject"]["value"]
        assert "化学" in s["subject"]["value"]
        assert "地理" in s["subject"]["value"]
