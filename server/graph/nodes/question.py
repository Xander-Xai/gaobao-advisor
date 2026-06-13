"""Question generation node — asks the user for missing info."""
from __future__ import annotations

from typing import Any

# Question bank: field -> question text, per scene
QUESTION_BANK: dict[str, dict[str, str]] = {
    "gaokao": {
        "province": "请问您是哪个省的考生呢？",
        "score": "请问您的高考分数是多少分？",
        "subject": "请问您是文科还是理科？或者新高考选科组合是什么？",
        "interest": "请问您对哪些专业方向比较感兴趣呢？",
        "region": "您对学校所在地区有什么偏好吗？",
        "family": "能简单介绍一下您的家庭背景吗？（如城市/农村、是否有体制内资源等）",
        "goal": "您未来有什么规划呢？比如考研、出国、就业还是考公？",
    },
    "kaoyan": {
        "interest": "请问您想考哪个专业方向的研究生呢？",
        "goal": "请问您的目标院校是哪里？或者对学校层次有什么要求？",
    },
    "career": {
        "interest": "请问您对哪些职业方向比较感兴趣？",
    },
    "general": {},
}


def question_generate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate a reply asking the user to fill in missing fields.

    Picks questions for the missing fields and builds a friendly
    multi-question reply.
    """
    scene = state.get("scene", "general")
    missing = state.get("missing_fields", [])
    bank = QUESTION_BANK.get(scene, QUESTION_BANK["general"])

    questions = []
    for field in missing:
        q = bank.get(field)
        if q:
            questions.append(q)

    if not questions:
        questions.append("请问还有什么我可以帮您了解的吗？")

    reply = "\n".join(questions)

    trace = list(state.get("trace", []))
    trace.append({
        "node": "question_generate",
        "event": f"questions_asked={len(questions)}",
    })
    return {"reply": reply, "trace": trace}
