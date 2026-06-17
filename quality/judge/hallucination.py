"""hallucination — 幻觉检测器。

基于规则的幻觉检测，识别 AI 回答中可能编造的数字、实体和缺失的来源引用。
"""

from __future__ import annotations

import re
from typing import Any


class HallucinationDetector:
    """幻觉检测器 — 检测 AI 回答中的潜在幻觉。"""

    # ── 数字+单位模式 ────────────────────────────────────────────────
    _NUMERIC_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(\d+\.?\d*)\s*分"),       # 分数: 680分, 92.5分
        re.compile(r"(\d+\.?\d*)\s*元"),        # 金额: 5000元
        re.compile(r"(\d+\.?\d*)\s*%"),         # 百分比: 95%
        re.compile(r"(\d+\.?\d*)\s*万人?"),     # 人数: 10万
        re.compile(r"(\d+\.?\d*)\s*个"),        # 数量: 3个
        re.compile(r"(\d{4})\s*年"),            # 年份: 2024年
        re.compile(r"(\d+\.?\d*)\s*倍"),        # 倍数: 3倍
        re.compile(r"(\d+\.?\d*)\s*名"),        # 排名: 第5名
        re.compile(r"(\d+\.?\d*)\s*所"),        # 学校数: 10所
        re.compile(r"(\d+\.?\d*)\s*条"),        # 条数: 5条
    ]

    # ── 学校名称模式 ────────────────────────────────────────────────
    _SCHOOL_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"([一-鿿]{2,6}大学)"),
        re.compile(r"([一-鿿]{2,6}学院)"),
        re.compile(r"([一-鿿]{2,4}师范[一-鿿]{0,4})"),
        re.compile(r"([一-鿿]{2,4}理工[一-鿿]{0,4})"),
        re.compile(r"([一-鿿]{2,4}工业[一-鿿]{0,2}大学)"),
        re.compile(r"([一-鿿]{2,4}农业[一-鿿]{0,2}大学)"),
        re.compile(r"([一-鿿]{2,4}医科[一-鿿]{0,2}大学)"),
        re.compile(r"([一-鿿]{2,4}财经[一-鿿]{0,2}大学)"),
        re.compile(r"([一-鿿]{2,4}政法[一-鿿]{0,2}大学)"),
    ]

    # ── 学校名中不应出现的动词/修饰词/连词 ─────────────────────────
    _SCHOOL_VERB_PREFIXES: tuple[str, ...] = (
        "推荐", "考虑", "选择", "可以", "应该", "还是", "或者",
        "如果", "但是", "虽然", "不过", "建议", "报考", "填报",
        "关注", "了解", "看看", "比较", "优先", "避免",
        "和", "与", "及", "和", "、", "，", "。",
    )

    # ── 专业名称模式 ────────────────────────────────────────────────
    _MAJOR_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?<![一-鿿])([一-鿿]{2,6}(?:工程|科学|技术|管理|经济|教育|医学|法学|文学|艺术|学))"),
    ]

    # ── 来源引用模式 ────────────────────────────────────────────────
    _SOURCE_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"数据显示[，,]?\s*"),
        re.compile(r"据统计[，,]?\s*"),
        re.compile(r"根据统计[，,]?\s*"),
        re.compile(r"研究表明[，,]?\s*"),
        re.compile(r"调查发现[，,]?\s*"),
        re.compile(r"有关报告[，,]?\s*"),
        re.compile(r"权威数据显示[，,]?\s*"),
        re.compile(r"官方数据[，,]?\s*"),
    ]

    # ── 来源引用后续模式（有来源的标志） ─────────────────────────────
    _ATTRIBUTION_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"来源[：:]\s*\S+"),
        re.compile(r"据《[^》]+》"),
        re.compile(r"根据[《<][^》>]+[》>]"),
        re.compile(r"教育部(?:公告|通知|文件)"),
        re.compile(r"阳光高考"),
        re.compile(r"各省(?:招生|考试)(?:院|中心|办)"),
        re.compile(r"中国教育在线"),
    ]

    def detect(
        self,
        reply: str,
        query: str = "",
        knowledge_chunks: str | None = None,
    ) -> list[str]:
        """检测 AI 回答中的潜在幻觉。

        Args:
            reply: AI 生成的回答。
            query: 用户原始问题（暂未使用，预留扩展）。
            knowledge_chunks: 知识库参考文本。

        Returns:
            幻觉标记列表，如 ["numeric:680", "entity_school:某某大学", "source_missing"]。
        """
        if not reply or not reply.strip():
            return []

        flags: list[str] = []
        knowledge_text = knowledge_chunks or ""

        # 1. 数字幻觉检测
        flags.extend(self._detect_numeric_hallucination(reply, knowledge_text))

        # 2. 实体幻觉检测
        flags.extend(self._detect_entity_hallucination(reply, knowledge_text))

        # 3. 来源引用缺失检测
        flags.extend(self._detect_source_attribution_missing(reply))

        return flags

    def _detect_numeric_hallucination(
        self, reply: str, knowledge_text: str
    ) -> list[str]:
        """检测数字幻觉 — 回复中的数字是否出现在知识库中。"""
        flags: list[str] = []

        for pattern in self._NUMERIC_PATTERNS:
            for match in pattern.finditer(reply):
                full_match = match.group(0)
                number = match.group(1)

                # 年份通常不需要验证
                if "年" in full_match and re.match(r"^\d{4}$", number):
                    continue

                # 检查数字是否出现在知识库中
                if knowledge_text and number not in knowledge_text:
                    # 提取完整匹配中的数字+单位作为标记
                    flag_value = re.sub(r"\s+", "", full_match)
                    flags.append(f"numeric:{flag_value}")

        return flags

    def _detect_entity_hallucination(
        self, reply: str, knowledge_text: str
    ) -> list[str]:
        """检测实体幻觉 — 学校/专业名称是否出现在知识库中。"""
        flags: list[str] = []

        # 学校名称检测
        seen_schools: set[str] = set()
        for pattern in self._SCHOOL_PATTERNS:
            for match in pattern.finditer(reply):
                school = self._strip_verb_prefix(match.group(1))
                if not school or school in seen_schools:
                    continue
                seen_schools.add(school)

                # 常见学校白名单（无需验证）
                if self._is_common_school(school):
                    continue

                if knowledge_text and school not in knowledge_text:
                    flags.append(f"entity_school:{school}")

        # 专业名称检测
        seen_majors: set[str] = set()
        for pattern in self._MAJOR_PATTERNS:
            for match in pattern.finditer(reply):
                major = self._strip_verb_prefix(match.group(1))
                if not major or major in seen_majors:
                    continue
                seen_majors.add(major)

                # 过滤过短的匹配（可能是误匹配）
                if len(major) < 3:
                    continue

                if knowledge_text and major not in knowledge_text:
                    flags.append(f"entity_major:{major}")

        return flags

    def _detect_source_attribution_missing(self, reply: str) -> list[str]:
        """检测来源引用缺失 — 使用了"数据显示"等表述但未给出具体来源。"""
        flags: list[str] = []

        for pattern in self._SOURCE_PATTERNS:
            for match in pattern.finditer(reply):
                start = match.end()
                # 检查后续 50 个字符内是否有来源引用
                after_text = reply[start : start + 50]

                has_attribution = any(
                    attr.search(after_text) for attr in self._ATTRIBUTION_PATTERNS
                )

                if not has_attribution:
                    flags.append("source_missing")
                    return flags  # 只需标记一次

        return flags

    @staticmethod
    def _strip_verb_prefix(name: str) -> str:
        """去除匹配到的实体名中的动词前缀。

        正则可能匹配到"推荐考虑浙江大学"，需要提取"浙江大学"。
        """
        for prefix in HallucinationDetector._SCHOOL_VERB_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name

    @staticmethod
    def _is_common_school(name: str) -> bool:
        """判断是否为常见知名学校（白名单，无需验证）。"""
        common = {
            "清华大学", "北京大学", "复旦大学", "上海交通大学",
            "浙江大学", "南京大学", "中国科学技术大学", "武汉大学",
            "华中科技大学", "中山大学", "四川大学", "山东大学",
            "同济大学", "东南大学", "天津大学", "南开大学",
            "厦门大学", "吉林大学", "中南大学", "湖南大学",
            "重庆大学", "兰州大学", "中国人民大学", "北京师范大学",
            "华东师范大学", "北京航空航天大学", "北京理工大学",
            "哈尔滨工业大学", "西安交通大学", "西北工业大学",
            "大连理工大学", "华南理工大学", "电子科技大学",
            "中国农业大学", "中国海洋大学", "中央民族大学",
            "国防科技大学", "东北大学", "郑州大学",
        }
        return name in common
