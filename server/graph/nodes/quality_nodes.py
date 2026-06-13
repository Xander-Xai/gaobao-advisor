"""Quality orchestration node — runs the full quality pipeline."""
from __future__ import annotations

from typing import Any

from server.services.quality import QualityOrchestrator

_orchestrator = None


def _get_orchestrator() -> QualityOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = QualityOrchestrator()
    return _orchestrator


def quality_orchestrate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run pre-generation quality checks.

    Detects emotion, selects cognitive models, recommends heuristics,
    and loads contextual knowledge.
    """
    orch = _get_orchestrator()
    text = state.get("input_text", "")
    slots = state.get("slots", {})

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

    trace = list(state.get("trace", []))
    trace.append({
        "node": "quality_orchestrate",
        "event": f"emotion={emotion_state}",
        "model": cognitive_model,
    })

    return {
        "emotion_state": emotion_state,
        "cognitive_model": cognitive_model,
        "decision_heuristics": decision_heuristics,
        "trace": trace,
    }
