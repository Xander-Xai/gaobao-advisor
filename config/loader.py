"""
LLM 配置加载器 — 从 YAML 配置文件 + 环境变量合并生成最终配置。

优先级: 环境变量 > YAML 文件 > 默认值

用法:
    from config.loader import load_llm_config
    CONFIG = load_llm_config()
"""

from __future__ import annotations

import os
from typing import Any


def _load_yaml_simple(path: str) -> dict[str, Any]:
    """极简 YAML 解析器（仅支持本项目需要的子集）。
    不引入 pyyaml 依赖，避免增加安装复杂度。
    支持: 嵌套字典、字符串/数字/null 值、带冒号的引号字符串。

    注意: 使用 partition(":") 只在第一个冒号处分割，因此
    "key: https://example.com:8080/v1" 会正确解析为 key="https://example.com:8080/v1"。
    但如果 VALUE 本身不含引号且包含冒号（如 "note: This is: important"），
    也会被正确解析，因为 partition 只分割第一个冒号。
    """
    result: dict[str, Any] = {}
    current_section: dict[str, Any] = result
    section_stack: list[tuple[int, dict]] = [(0, result)]

    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())
            raw = stripped.lstrip()

            # 回退到正确的父级
            while section_stack and indent <= section_stack[-1][0] and len(section_stack) > 1:
                section_stack.pop()
            current_section = section_stack[-1][1]

            if ":" in raw:
                key, _, value = raw.partition(":")
                key = key.strip()
                value = value.strip()

                if value == "" or value == "|":
                    # 子字典或列表开始
                    new_section: dict[str, Any] = {}
                    current_section[key] = new_section
                    section_stack.append((indent + 2, new_section))
                else:
                    current_section[key] = _parse_yaml_value(value)

    return result


def _parse_yaml_value(value: str) -> Any:
    """解析 YAML 值：字符串、数字、布尔、null。"""
    if value in ("null", "~", ""):
        return None
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    # 数字
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    # 去除引号
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_llm_config(config_path: str | None = None) -> dict[str, Any]:
    """加载 LLM 配置，合并 YAML + 环境变量。

    Args:
        config_path: YAML 配置文件路径。为 None 时使用默认路径。

    Returns:
        配置字典，包含 base_url, api_key, model, max_tokens, temperature, enable_search
    """
    # 确定 YAML 路径
    if config_path is None:
        config_path = os.environ.get(
            "LLM_CONFIG_PATH",
            os.path.join(os.path.dirname(__file__), "llm_providers.yaml"),
        )

    # 加载 YAML（如果存在）
    yaml_config: dict[str, Any] = {}
    if os.path.exists(config_path):
        yaml_config = _load_yaml_simple(config_path)

    providers = yaml_config.get("providers", {})
    defaults = yaml_config.get("defaults", {})

    # 确定当前 provider
    provider_name = os.getenv("LLM_PROVIDER", "").lower()
    if not provider_name:
        provider_name = defaults.get("provider", "deepseek")

    # 从 YAML 获取 provider 配置
    preset = providers.get(provider_name, {})

    # 默认值
    default_temp = defaults.get("temperature", 0.7)
    default_search = defaults.get("enable_search", True)

    # 合并: 环境变量 > YAML > 默认值
    enable_search_raw = os.getenv("ENABLE_SEARCH", "")
    if enable_search_raw:
        enable_search = enable_search_raw.lower() in ("true", "1", "yes")
    else:
        enable_search = default_search

    # temperature: 环境变量 > YAML > 默认值
    temp_raw = os.getenv("LLM_TEMPERATURE", "")
    if temp_raw:
        try:
            temperature = float(temp_raw)
        except (ValueError, TypeError):
            temperature = float(preset.get("temperature", default_temp))
    else:
        temperature = float(preset.get("temperature", default_temp))

    # max_tokens: 环境变量 > YAML > 默认值
    max_tokens_raw = os.getenv("LLM_MAX_TOKENS", "")
    if max_tokens_raw:
        try:
            max_tokens = int(max_tokens_raw)
        except (ValueError, TypeError):
            max_tokens = preset.get("max_tokens") or defaults.get("max_tokens")
    else:
        max_tokens = preset.get("max_tokens") or defaults.get("max_tokens")

    return {
        "base_url": os.getenv("LLM_BASE_URL") or preset.get("base_url", "https://api.deepseek.com"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL") or preset.get("model", "deepseek-chat"),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_search": enable_search,
    }
