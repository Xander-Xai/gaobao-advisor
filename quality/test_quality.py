"""
quality.emotion_detector 单元测试

运行: cd /home/dev/projects/gaobao/gaobao-advisor && python quality/test_quality.py
"""

import os
import sys

# 让 import 能找到项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from quality.ai_era_risk import get_major_risk, get_risk_summary
from quality.cross_validator import cross_validate_admission
from quality.emotion_detector import CRISIS_HOTLINES, EmotionDetector


class TestEmotionDetector(unittest.TestCase):
    """情绪检测器测试用例。"""

    def setUp(self):
        self.detector = EmotionDetector()

    # ------------------------------------------------------------------
    # 测试用例
    # ------------------------------------------------------------------

    def test_normal_input(self):
        """正常咨询 → 🟢 standard"""
        result = self.detector.detect("我是湖北考生，580分，想学计算机")
        self.assertEqual(result["level"], "🟢")
        self.assertEqual(result["strategy"], "standard")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["hint"], "")
        self.assertEqual(result["matched_keywords"], [])

    def test_anxious_input(self):
        """焦虑输入 → 至少 🟡 empathize_first（可能因子串匹配升至 🔴）"""
        text = "我考砸了，只有480分，好焦虑，不知道怎么办"
        result = self.detector.detect(text)
        # "好焦虑" 含 "焦虑"，"不知道怎么办" 含 "怎么办"，子串叠加可能触发 🔴
        self.assertIn(result["level"], ("🟡", "🔴"))
        self.assertIn("考砸了", result["matched_keywords"])
        self.assertIn("好焦虑", result["matched_keywords"])
        self.assertIn("不知道怎么办", result["matched_keywords"])
        self.assertGreaterEqual(result["score"], 30)

    def test_breakdown_input(self):
        """崩溃输入 → 🔴 crisis"""
        text = "我完蛋了，才考了350分，这辈子没救了，不想活了"
        result = self.detector.detect(text)
        self.assertEqual(result["level"], "🔴")
        self.assertEqual(result["strategy"], "crisis")
        self.assertIn("完蛋了", result["matched_keywords"])
        self.assertIn("没救了", result["matched_keywords"])
        self.assertIn("不想活了", result["matched_keywords"])
        self.assertGreaterEqual(result["score"], 70)
        self.assertIn("心理热线", result["hint"])

    def test_compound_emotion(self):
        """复合情绪（焦虑+迷茫） → 🟡 或 🔴"""
        text = "好焦虑好迷茫，不知道怎么办，怕选错专业毁了一辈子"
        result = self.detector.detect(text)
        # 多个中危关键词叠加，应达到 🟡 以上
        self.assertIn(result["level"], ("🟡", "🔴"))
        self.assertGreaterEqual(result["score"], 30)
        self.assertIn("好焦虑", result["matched_keywords"])
        self.assertIn("迷茫", result["matched_keywords"])
        self.assertIn("不知道怎么办", result["matched_keywords"])
        self.assertIn("怕选错", result["matched_keywords"])

    def test_empty_input(self):
        """空输入 → 🟢, score=0"""
        result = self.detector.detect("")
        self.assertEqual(result["level"], "🟢")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["strategy"], "standard")
        self.assertEqual(result["matched_keywords"], [])
        self.assertEqual(result["hint"], "")

    def test_score_cap_100(self):
        """分数上限为 100"""
        # 故意堆叠很多高危词
        text = "崩溃完蛋了没救了想死不想活废了绝望活不下去没有希望不想活了想自杀想结束不想读了这辈子完了彻底完蛋"
        result = self.detector.detect(text)
        self.assertLessEqual(result["score"], 100)

    def test_crisis_hotlines_constant(self):
        """CRISIS_HOTLINES 常量不为空"""
        self.assertIsInstance(CRISIS_HOTLINES, list)
        self.assertGreater(len(CRISIS_HOTLINES), 0)

    def test_strategy_at_boundary(self):
        """刚好 30 分 → 🟡, 刚好 70 分 → 🔴"""
        # 2 个中危词 × 15 = 30 → 🟡
        result_30 = self.detector.detect("焦虑 害怕")
        self.assertEqual(result_30["level"], "🟡")
        self.assertEqual(result_30["score"], 30)

        # 需要 70 分: 2 高危(60) + 1 中危(15) → 75 ≥ 70 → 🔴
        # 但精确 70 很难凑，这里测试 ≥70 的情况
        result_70 = self.detector.detect("崩溃 完蛋了 焦虑")
        self.assertEqual(result_70["level"], "🔴")
        self.assertGreaterEqual(result_70["score"], 70)


class TestCrossValidator(unittest.TestCase):
    """cross_validate_admission 测试用例。"""

    def test_cross_validate_consistent(self):
        """2 sources with scores 600/598 → confidence="高"."""
        result = cross_validate_admission([
            {"source": "DB", "min_score": 600, "min_rank": 1000},
            {"source": "API", "min_score": 598, "min_rank": 1005},
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], "高")
        self.assertEqual(result["note"], "")
        self.assertEqual(result["sources_used"], ["DB", "API"])

    def test_cross_validate_inconsistent(self):
        """2 sources with scores 600/580 → confidence="中", note contains diff info."""
        result = cross_validate_admission([
            {"source": "DB", "min_score": 600, "min_rank": 1000},
            {"source": "Search", "min_score": 580, "min_rank": 1200},
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], "中")
        self.assertIn("差异", result["note"])

    def test_cross_validate_single_source(self):
        """1 source → confidence="低"."""
        result = cross_validate_admission([
            {"source": "DB", "min_score": 590, "min_rank": 800},
        ])
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], "低")
        self.assertIn("仅单源", result["note"])

    def test_cross_validate_no_sources(self):
        """Empty list → None."""
        self.assertIsNone(cross_validate_admission([]))

    def test_cross_validate_no_scores(self):
        """Sources without min_score → None."""
        self.assertIsNone(cross_validate_admission([
            {"source": "DB", "min_score": None, "min_rank": 1000},
            {"source": "API", "min_score": None, "min_rank": 1200},
        ]))


class TestAiEraRisk(unittest.TestCase):
    """AI时代专业风险评估测试用例。"""

    def test_get_risk_known_major(self):
        """计算机科学与技术 → not None, risk_zone="🟡"."""
        risk = get_major_risk("计算机科学与技术")
        self.assertIsNotNone(risk)
        self.assertEqual(risk["risk_zone"], "🟡")

    def test_get_risk_red_zone(self):
        """金融学 → risk_zone="🔴"."""
        risk = get_major_risk("金融学")
        self.assertIsNotNone(risk)
        self.assertEqual(risk["risk_zone"], "🔴")

    def test_get_risk_green_zone(self):
        """电气工程及其自动化 → risk_zone="🟢"."""
        risk = get_major_risk("电气工程及其自动化")
        self.assertIsNotNone(risk)
        self.assertEqual(risk["risk_zone"], "🟢")

    def test_get_risk_unknown_major(self):
        """量子玄学 → None."""
        risk = get_major_risk("量子玄学")
        self.assertIsNone(risk)

    def test_get_risk_summary(self):
        """金融学 → summary string <= 80 chars containing '🔴' or '高'."""
        summary = get_risk_summary("金融学")
        self.assertIsNotNone(summary)
        self.assertLessEqual(len(summary), 80)
        self.assertTrue("🔴" in summary or "高" in summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
