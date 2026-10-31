"""Intent detection node — identifies scene from user input."""

from __future__ import annotations

from typing import Any

# Keywords that signal each scene
_SCENE_KEYWORDS: dict[str, list[str]] = {
    "kaoyan": ["考研", "研究生", "保研", "复试", "初试", "调剂"],
    "career": ["就业", "工作", "实习", "职业", "行业", "考公"],
    "gaokao": ["高考", "志愿", "填报", "录取", "分数线", "投档", "考生"],
}

# Terms that mark a question as answerable from the knowledge corpus rather
# than (or in addition to) the structured admissions database. This is a
# cheap, explicit router signal — not a classifier — and deliberately errs
# towards running BOTH the SQL and RAG paths.
_KNOWLEDGE_KEYWORDS: list[str] = [
    "什么是",
    "是什么",
    "含义",
    "怎么理解",
    "规则",
    "政策",
    "流程",
    "区别",
    "介绍一下",
    "解释",
    "平行志愿",
    "顺序志愿",
    "征集志愿",
    "退档",
    "滑档",
    "投档",
    "服从调剂",
    "一分一段",
    "位次法",
    "冲稳保",
    "选科",
    "赋分",
    "强基",
    "专项计划",
    "专升本",
    "考研",
    "保研",
    "调剂",
    "院校层次",
    "专业选择",
    "就业前景",
    "就业路径",
    "转专业",
    "专科",
    "高职",
]


def _looks_like_knowledge_question(text: str) -> bool:
    return any(kw in text for kw in _KNOWLEDGE_KEYWORDS)


def intent_detect_node(state: dict[str, Any]) -> dict[str, Any]:
    """Detect the user's intent scene from input text.

    If a scene is already set in state and is not 'general', keep it.
    Otherwise, scan keywords to determine the scene.  Defaults to 'gaokao'.
    Also records whether the input looks like a knowledge question.
    """
    text = state.get("input_text", "")
    knowledge_query = _looks_like_knowledge_question(text)

    current_scene = state.get("scene", "")
    if current_scene and current_scene != "general":
        trace = list(state.get("trace", []))
        trace.append(
            {
                "node": "intent_detect",
                "event": f"scene_pre_set={current_scene}",
                "knowledge_query": knowledge_query,
            }
        )
        return {"knowledge_query": knowledge_query, "trace": trace}

    detected = "gaokao"  # default

    for scene, keywords in _SCENE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected = scene
            break

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "intent_detect",
            "event": f"detected_scene={detected}",
            "knowledge_query": knowledge_query,
        }
    )
    return {"scene": detected, "knowledge_query": knowledge_query, "trace": trace}
