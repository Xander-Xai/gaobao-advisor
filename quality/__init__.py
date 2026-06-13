"""
quality — 拾贝高考志愿顾问 质量升级模块

提供情绪检测、回答质量评估等功能，
帮助 AI 在志愿填报对话中做出更人性化的回应。
"""

from .emotion_detector import CRISIS_HOTLINES, EmotionDetector, detect_emotion

__all__ = ["EmotionDetector", "CRISIS_HOTLINES", "detect_emotion"]
