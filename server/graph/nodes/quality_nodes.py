"""Quality orchestration node — runs the full quality pipeline."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from server.services.quality import QualityOrchestrator
from skills.service import SkillService

_orchestrator = None
_skill_service = None
_init_lock = threading.Lock()


def _get_orchestrator() -> QualityOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _init_lock:
            if _orchestrator is None:  # double-check
                _orchestrator = QualityOrchestrator()
    return _orchestrator


def _get_skill_service() -> SkillService:
    global _skill_service
    if _skill_service is None:
        with _init_lock:
            if _skill_service is None:  # double-check
                _skill_service = SkillService(skills_dir=Path(__file__).parents[2] / "skills")
    return _skill_service


def quality_orchestrate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run pre-generation quality checks.

    Detects emotion, selects cognitive models, recommends heuristics,
    loads contextual knowledge, and builds skill context for the scene.
    """
    orch = _get_orchestrator()
    skill_svc = _get_skill_service()
    text = state.get("input_text", "")
    slots = state.get("slots", {})
    scene = state.get("scene", "general")

    # Emotion detection
    emotion_result = orch.detect_emotion(text)
    emotion_state = emotion_result.get("level", "normal")

    # Model selection
    model_result = orch.select_models(slots, text)
    cognitive_model = model_result.get("model", "default")

    # Decision heuristics
    heuristics_raw = orch.recommend_heuristics(slots)
    decision_heuristics = [
        h.get("description", h.get("name", ""))
        for h in (heuristics_raw if isinstance(heuristics_raw, list) else [])
    ]

    # Skill context for the scene
    skill_context = skill_svc.build_context(scene)

    trace = list(state.get("trace", []))
    trace.append({
        "node": "quality_orchestrate",
        "event": f"emotion={emotion_state}",
        "model": cognitive_model,
        "skill_scene": scene,
    })

    return {
        "emotion_state": emotion_state,
        "cognitive_model": cognitive_model,
        "decision_heuristics": decision_heuristics,
        "knowledge_context": skill_context,
        "trace": trace,
    }