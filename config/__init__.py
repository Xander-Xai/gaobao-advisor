"""gaobao-advisor 配置系统 — 统一入口。

用法:
    from config import get_config

    config = get_config()
    brand = config["brand"]["brand"]   # 品牌基础信息
    report = config["brand"]["report"]  # 报告相关配置
    tuning = config["tuning"]           # 策略参数
    llm = config["llm"]                 # LLM 配置
"""

from __future__ import annotations

from typing import Any

from config.loader import load_brand, load_llm_config, load_runtime_settings, load_tuning, load_voice_config

_CONFIG_CACHE: dict[str, Any] | None = None


def get_config(reload: bool = False) -> dict[str, Any]:
    """返回完整的统一配置字典（带缓存）。

    Args:
        reload: 强制重新加载（跳过缓存）

    Returns:
        配置字典，包含 brand / tuning / llm 三个子字典
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None or reload:
        _CONFIG_CACHE = {
            "brand": load_brand(),
            "tuning": load_tuning(),
            "llm": load_llm_config(),
            "runtime": load_runtime_settings(),
            "voice": load_voice_config(),
        }
    return _CONFIG_CACHE
