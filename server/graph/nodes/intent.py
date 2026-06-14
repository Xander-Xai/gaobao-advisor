"""Intent detection node — identifies scene from user input."""

from __future__ import annotations

from typing import Any

# Keywords that signal each scene
_SCENE_KEYWORDS: dict[str, list[str]] = {
    "kaoyan": ["考研", "研究生", "保研", "复试", "初试", "调剂"],
    "career": ["就业", "工作", "实习", "求职", "面试", "简历", "职业"],
    "gaokao": ["高考", "志愿", "填报", "录取", "分数线", "投档", "考生"],
}


def intent_detect_node(state: dict[str, Any]) -> dict[str, Any]:
    """Detect the user's intent scene from input text.

    If a scene is already set in state and is not 'general', keep it.
    Otherwise, scan keywords to determine the scene.  Defaults to 'gaokao'.
    """
    current_scene = state.get("scene", "")
    if current_scene and current_scene != "general":
        trace = list(state.get("trace", []))
        trace.append({"node": "intent_detect", "event": f"scene_pre_set={current_scene}"})
        return {"trace": trace}

    text = state.get("input_text", "")
    detected = "gaokao"  # default

    for scene, keywords in _SCENE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected = scene
            break

    trace = list(state.get("trace", []))
    trace.append({"node": "intent_detect", "event": f"detected_scene={detected}"})
    return {"scene": detected, "trace": trace}
