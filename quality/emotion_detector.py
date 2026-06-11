"""
情绪检测模块 — 基于关键词的加权情绪评分

零成本实现（纯 Python，无 LLM 调用），
用于在高考志愿填报场景中识别学生的情绪状态，
以便 AI 给出更有同理心的回应策略。

评分规则:
  - 🔴 高危关键词 (+30): 涉及崩溃、绝望、自杀等
  - 🟡 中危关键词 (+15): 涉及焦虑、迷茫、压力等
  - 🟢 低危关键词 (+5):  涉及紧张、犹豫等

返回结果:
  level   — 情绪等级 emoji
  score   — 加权总分（上限 100）
  strategy — 对应回复策略
  matched_keywords — 命中的关键词列表
  hint    — 回复提示
"""

CRISIS_HOTLINES: list[str] = [
    "全国心理援助热线：400-161-9995",
    "北京心理危机研究与干预中心：010-82951332",
    "希望24热线：400-161-9995",
    "生命热线：400-821-1215",
]

# 三级关键词权重表
_KEYWORD_TIERS: list[tuple[list[str], int]] = [
    # 🔴 高危 (+30)
    (
        [
            "崩溃", "完蛋了", "没救了", "想死", "不想活", "废了",
            "绝望", "活不下去", "没有希望", "不想活了", "想自杀",
            "想结束", "不想读了", "这辈子完了", "彻底完蛋",
        ],
        30,
    ),
    # 🟡 中危 (+15)
    (
        [
            "焦虑", "害怕", "很怕", "担心", "迷茫", "不知道怎么办",
            "考砸了", "考差了", "复读", "压力大", "睡不着",
            "心态崩了", "没信心", "不自信", "怕选错", "怎么办",
            "好迷茫", "好焦虑",
            # 方言感叹词
            "完犊子了", "整不会了", "可咋整", "愁死了",
        ],
        15,
    ),
    # 🟢 低危 (+5)
    (
        ["紧张", "纠结", "犹豫", "不太确定", "有点慌", "不确定",
         "美滋滋", "稳了", "信心满满", "稳稳的"],
        5,
    ),
]


class EmotionDetector:
    """关键词情绪检测器（无外部依赖）。"""

    def __init__(self) -> None:
        self._tiers = _KEYWORD_TIERS

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def detect(self, text: str) -> dict:
        """
        分析文本的情绪等级。

        Parameters
        ----------
        text : str
            用户输入的原始文本。

        Returns
        -------
        dict
            {
                "level": "🟢" | "🟡" | "🔴",
                "score": int,          # 0-100
                "strategy": str,       # standard | empathize_first | crisis
                "matched_keywords": list[str],
                "hint": str,
            }
        """
        if not text or not text.strip():
            return self._build_result(
                score=0,
                matched=[],
            )

        matched: list[str] = []
        total: int = 0

        for keywords, weight in self._tiers:
            for kw in keywords:
                if kw in text:
                    matched.append(kw)
                    total += weight

        # 分数范围 0-100
        score = max(0, min(total, 100))

        return self._build_result(score=score, matched=matched)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(*, score: int, matched: list[str]) -> dict:
        """根据分数返回完整的情绪字典。"""
        if score >= 70:
            return {
                "level": "🔴",
                "score": score,
                "strategy": "crisis",
                "matched_keywords": matched,
                "hint": "接住情绪→锚定→心理热线→方案",
            }
        if score >= 30:
            return {
                "level": "🟡",
                "score": score,
                "strategy": "empathize_first",
                "matched_keywords": matched,
                "hint": "先共情1句再分析",
            }
        return {
            "level": "🟢",
            "score": score,
            "strategy": "standard",
            "matched_keywords": matched,
            "hint": "",
        }


# ── 模块级便捷函数（供 agent.py 直接 import） ──
_detector_instance = EmotionDetector()


def detect_emotion(text: str) -> dict:
    """便捷函数：detect_emotion(text) → 情绪检测结果 dict。"""
    return _detector_instance.detect(text)
