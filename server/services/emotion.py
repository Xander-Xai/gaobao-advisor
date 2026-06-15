"""
Emotion detection service wrapper.

Thin wrapper around quality.emotion_detector that exposes a clean,
lazy-initialized interface for the server layer.
"""

from __future__ import annotations

from typing import Any

_detector = None


def _get_detector():
    """Lazy-init the EmotionDetector singleton."""
    global _detector
    if _detector is None:
        from quality.emotion_detector import EmotionDetector

        _detector = EmotionDetector()
    return _detector


def detect_emotion(text: str) -> dict[str, Any]:
    """Detect emotion in user text.

    Returns:
        dict with keys: level, score, strategy, matched_keywords, hint
    """
    return _get_detector().detect(text)


def get_crisis_hotlines() -> list[str]:
    """Return crisis hotline numbers."""
    from quality.emotion_detector import CRISIS_HOTLINES

    return list(CRISIS_HOTLINES)
