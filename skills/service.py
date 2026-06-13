"""Skill methodology service — loads skill files and builds strategy/context."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Scene(str, Enum):
    """Supported conversation scenes."""
    GAOKAO = "gaokao"
    KAO_YAN = "kaoyan"
    CAREER = "career"
    GENERAL = "general"


# Maximum number of missing fields to display in prompts
_MAX_DISPLAY_FIELDS = 3


class SkillStrategy(BaseModel):
    """Structured strategy output for a scene."""
    scene: str
    heuristics: list[str] = Field(default_factory=list)
    output_style: list[str] = Field(default_factory=list)
    answer_rules: list[str] = Field(default_factory=list)


# Default skill files to load per scene
_SKILL_FILES = [
    "mental_models.md",
    "heuristics.md",
    "anti_patterns.md",
    "expression_engine.md",
    "safety_rules.md",
]

# Strategy content extracted from skill files
_GAOKAO_HEURISTICS = [
    "灵魂追问：先把关键约束问透，再给方案。",
    "中位数原则：不看顶尖样本，只看普通学生毕业后的主流去向。",
    "就业倒推法：从5年后的就业和薪资中位数倒推今天的选择。",
    "家庭背景分流：普通家庭先保确定性，有试错资本再谈热爱。",
    "500强测试：别听企业怎么说，要看企业去哪里招、招什么人。",
    "城市优先：同档次下优先看资源密度更高、机会更多的城市。",
    "不可替代性检验：工资和不可替代性成正比。",
    "10年压迫测试：能不能接受孩子工作十年后收入不如当初分数更低的人。",
]

_GAOKAO_OUTPUT_STYLE = [
    "直接，短句、先结论后展开。",
    "先讲现实，再讲选择，不说空话。",
    "用第一人称给判断，不绕弯子。",
    "要有压迫感和推进感，但不胡编数据。",
    "开场用8种模板之一，不重复。",
    "节奏：铺垫→反转→金句。",
    "每3-4段至少1个反问。",
    "收尾有≤30字金句。",
]

_GAOKAO_ANSWER_RULES = [
    "凡是学校，专业、就业、政策问题，优先查本地数据库，其次查百度高考API。",
    "结论必须明确，不能只讲正确的废话。",
    "不能拿极端成功样本替普通家庭做决策。",
    "没有确认过的精确数字，宁可说趋势，也不能硬编。",
    "绝对禁止：或许/可能/这取决于/综合评估/建议您/仅供参考。",
    "数据必须标注来源和年份。",
    "每次推荐末尾必须附免责声明。",
]


class SkillService:
    """Load skill markdown files and build scene-specific strategy/context."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path(__file__).parent
        self._loaded = False
        self._mental_models = ""
        self._heuristics_text = ""
        self._anti_patterns = ""
        self._expression_engine = ""
        self._safety_rules = ""

    def load_assets(self) -> None:
        """Load all skill markdown files. Idempotent."""
        if self._loaded:
            return

        gaokao_dir = self._skills_dir / "gaokao"
        if not gaokao_dir.exists():
            self._loaded = True
            return

        self._mental_models = self._read(gaokao_dir / "mental_models.md")
        self._heuristics_text = self._read(gaokao_dir / "heuristics.md")
        self._anti_patterns = self._read(gaokao_dir / "anti_patterns.md")
        self._expression_engine = self._read(gaokao_dir / "expression_engine.md")
        self._safety_rules = self._read(gaokao_dir / "safety_rules.md")
        self._loaded = True

    def _read(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def build_strategy(self, scene: str) -> SkillStrategy:
        """Build a structured strategy for the given scene."""
        self.load_assets()
        if scene == Scene.GAOKAO:
            return SkillStrategy(
                scene=scene,
                heuristics=_GAOKAO_HEURISTICS,
                output_style=_GAOKAO_OUTPUT_STYLE,
                answer_rules=_GAOKAO_ANSWER_RULES,
            )
        return SkillStrategy(scene=scene)

    def build_context(self, scene: str) -> str:
        """Build a context string to inject into the LLM system message."""
        self.load_assets()

        parts: list[str] = []

        if self._safety_rules:
            parts.append(self._safety_rules)

        if scene == Scene.GAOKAO:
            if self._mental_models:
                parts.append(self._mental_models)
            if self._heuristics_text:
                parts.append(self._heuristics_text)
            if self._anti_patterns:
                parts.append(self._anti_patterns)
            if self._expression_engine:
                parts.append(self._expression_engine)
        else:
            if self._mental_models:
                parts.append(self._mental_models)

        return "\n\n---\n\n".join(parts) if parts else ""

    def build_question_reply(self, scene: str, missing_fields: list[str]) -> str:
        """Build a natural-language question reply for missing fields."""
        self.load_assets()

        field_labels = {
            "province": "省份",
            "score": "分数",
            "subject": "选科",
            "interest": "专业兴趣",
            "region": "地域偏好",
            "family": "家庭资源",
            "goal": "核心诉求",
        }

        lead = {
            Scene.GAOKAO: "你先别急着让我直接报学校。",
            Scene.KAO_YAN: "你先别急着定考研还是就业。",
            Scene.CAREER: "你先别急着换方向。",
        }.get(scene, "你先别急着下结论。")

        labels = [field_labels.get(f, f) for f in missing_fields[:_MAX_DISPLAY_FIELDS]]
        if not labels:
            return f"{lead} 你先把情况说说，我帮你看看。"

        missing_text = "、".join(labels)
        return (
            f"{lead} "
            f"关键条件还差{missing_text}，这些没锁准我不会给你拍脑袋的答案。"
            f"你先把{labels[0]}告诉我，我再往下走。"
        )