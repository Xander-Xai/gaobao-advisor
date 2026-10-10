"""
LLM 配置加载器 — 从 YAML 配置文件 + 环境变量合并生成最终配置。

优先级: 环境变量 > YAML 文件 > 默认值

用法:
    from config.loader import load_llm_config
    CONFIG = load_llm_config()
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


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
            # 严格小于: 相同缩进为同级（不pop），更深缩进为子级（不pop），更浅缩进才回退
            while section_stack and indent < section_stack[-1][0] and len(section_stack) > 1:
                section_stack.pop()
            current_section = section_stack[-1][1]

            if ":" in raw:
                key, _, value = raw.partition(":")
                key = key.strip()
                value = value.strip()

                if value == "" or value == "|":
                    # 子字典开始
                    new_section: dict[str, Any] = {}
                    current_section[key] = new_section
                    section_stack.append((indent + 2, new_section))
                else:
                    current_section[key] = _parse_yaml_value(value)
            elif raw.startswith("- ") and len(section_stack) > 1:
                # 列表项: 追加到父级字典的 _list 键
                item_val = _parse_yaml_value(raw[2:].strip())
                parent = section_stack[-1][1]
                if "_items" not in parent:
                    parent["_items"] = []
                parent["_items"].append(item_val)

    return _post_process_lists(result)


def _post_process_lists(d: dict[str, Any]) -> dict[str, Any]:
    """Convert {_items: [...]} back to plain lists in nested dicts."""
    for key, value in list(d.items()):
        if isinstance(value, dict):
            if "_items" in value:
                d[key] = value["_items"]
            else:
                _post_process_lists(value)
    return d


def _parse_yaml_value(value: str) -> Any:
    """解析 YAML 值：字符串、数字、布尔、null、内联列表。"""
    if value in ("null", "~", ""):
        return None
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    # 内联列表 [a, b, c]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_yaml_value(p.strip()) for p in _split_yaml_list(inner)]
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


def _split_yaml_list(text: str) -> list[str]:
    """Split a YAML inline list by comma, respecting quoted strings.

    Example: '"金融", "法学", "新闻"' -> ['"金融"', '"法学"', '"新闻"']
    """
    parts: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
        elif ch == "," and in_quote is None:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [p for p in parts if p]


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
        provider_name = defaults.get("provider", "demo")

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

    base_url = os.getenv("LLM_BASE_URL") or preset.get("base_url", "demo://local")

    # SSRF defense: warn if base_url points to private/internal network
    try:
        from server.middleware.security import check_ssrf

        if check_ssrf(base_url):
            logger.warning("LLM base_url %s resolves to a private/internal address — potential SSRF risk", base_url)
    except Exception:
        pass  # SSRF check is defense-in-depth; don't block config loading on it

    return {
        "provider": provider_name,
        "base_url": base_url,
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL") or preset.get("model", "gaobao-demo"),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_search": enable_search,
        "providers": providers,
        "roles": yaml_config.get("roles", {}),
    }


def load_brand(config_path: str | None = None) -> dict[str, Any]:
    """加载品牌配置。

    优先级: 环境变量 > brand.yaml > 默认值

    Args:
        config_path: brand.yaml 路径。为 None 时使用默认路径。
    """
    if config_path is None:
        config_path = os.environ.get(
            "GAOBAO__BRAND_CONFIG_PATH",
            os.path.join(os.path.dirname(__file__), "brand.yaml"),
        )

    current_year = datetime.now().year
    brand: dict[str, Any] = {
        "brand": {"name": "高考志愿AI顾问", "copyright": "© 高考志愿AI顾问"},
        "report": {"year": current_year, "cover_title": "金榜题名"},
    }
    if os.path.exists(config_path):
        loaded = _load_yaml_simple(config_path)
        _deep_merge(brand, loaded)

    # 环境变量覆盖
    env_override = os.getenv("GAOBAO__BRAND__NAME", "")
    if env_override:
        _deep_set(brand, ["brand", "name"], env_override)

    env_year = os.getenv("GAOBAO__BRAND__REPORT_YEAR", "")
    if env_year:
        try:
            _deep_set(brand, ["report", "year"], int(env_year))
        except (ValueError, TypeError):
            pass

    return brand


def load_tuning(config_path: str | None = None) -> dict[str, Any]:
    """加载策略参数配置。

    优先级: 环境变量 > tuning.yaml > 默认值
    """
    if config_path is None:
        config_path = os.environ.get(
            "GAOBAO__TUNING_CONFIG_PATH",
            os.path.join(os.path.dirname(__file__), "tuning.yaml"),
        )

    tuning: dict[str, Any] = {}
    if os.path.exists(config_path):
        tuning = _load_yaml_simple(config_path)

    # 环境变量覆盖（核心参数）
    _override_from_env(tuning, "GAOBAO__RAG__VECTOR_WEIGHT", ["rag", "vector_weight"], float)
    _override_from_env(tuning, "GAOBAO__RAG__KEYWORD_WEIGHT", ["rag", "keyword_weight"], float)
    _override_from_env(tuning, "GAOBAO__RATE_LIMIT__RATE", ["rate_limit", "per_ip_per_second"], int)
    _override_from_env(tuning, "GAOBAO__RATE_LIMIT__BURST", ["rate_limit", "burst_capacity"], int)

    return tuning


def load_runtime_settings() -> dict[str, Any]:
    """Load filesystem and deployment settings with sane defaults."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.getenv("GAOBAO__DATA_DIR", os.path.join(project_root, "data"))

    cors_origins_raw = os.getenv("CORS_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    if not cors_origins:
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:3080",
            "http://localhost:5173",
            "http://localhost:8000",
        ]

    return {
        "app_env": os.getenv("APP_ENV", "development").lower(),
        "project_root": project_root,
        "data_dir": data_dir,
        "db_path": os.getenv("GAOBAO__DB_PATH", os.path.join(data_dir, "gaokao.db")),
        "analytics_db_path": os.getenv("GAOBAO__ANALYTICS_DB_PATH", os.path.join(data_dir, "analytics.db")),
        "reports_dir": os.getenv("GAOBAO__REPORTS_DIR", os.path.join(data_dir, "reports")),
        "vector_index_dir": os.getenv("GAOBAO__VECTOR_INDEX_DIR", os.path.join(data_dir, "vector_index")),
        "session_secret_file": os.getenv("GAOBAO__SESSION_SECRET_FILE", os.path.join(data_dir, ".session_secret")),
        "service_name": os.getenv("GAOBAO__SERVICE_NAME", "gaobao-advisor"),
        "api_prefix": os.getenv("GAOBAO__API_PREFIX", "/api/v1"),
        "cors_origins": cors_origins,
        "rag_enabled": _env_bool("ENABLE_RAG_KB", False),
        "voice_enabled": _env_bool("VOICE_ENABLED", False),
    }


def validate_deployment_settings() -> dict[str, Any]:
    """Validate unsafe deployment defaults before the application starts.

    Development mode remains usable without credentials. Production mode must
    fail closed when secrets or allowed browser origins are not explicit.
    """
    runtime = load_runtime_settings()
    if runtime["app_env"] != "production":
        return runtime

    errors: list[str] = []
    if not os.getenv("SESSION_SECRET", "").strip():
        errors.append("SESSION_SECRET must be set in production")
    if not os.getenv("CORS_ORIGINS", "").strip():
        errors.append("CORS_ORIGINS must be set in production")
    if runtime["voice_enabled"] and not (
        os.getenv("GAOBAO__VOICE__API_KEY", "").strip() or os.getenv("DASHSCOPE_CHAT_API_KEY", "").strip()
    ):
        errors.append("VOICE_ENABLED requires GAOBAO__VOICE__API_KEY in production")

    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))
    return runtime


def _env_bool(name: str, default: bool) -> bool:
    """Parse a conventional boolean environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_voice_config() -> dict[str, Any]:
    """Load voice-rendering settings with portable defaults."""
    tuning = load_tuning().get("voice", {})
    return {
        "api_key": os.getenv("GAOBAO__VOICE__API_KEY")
        or os.getenv("DASHSCOPE_CHAT_API_KEY", "")
        or tuning.get("api_key", ""),
        "base_url": os.getenv("GAOBAO__VOICE__BASE_URL")
        or os.getenv("DASHSCOPE_CHAT_BASE_URL", "")
        or tuning.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model": os.getenv("GAOBAO__VOICE__MODEL")
        or os.getenv("DASHSCOPE_CHAT_MODEL", "")
        or tuning.get("model", "qwen-plus"),
        "temperature": float(os.getenv("GAOBAO__VOICE__TEMPERATURE") or tuning.get("temperature", 0.7)),
        "max_tokens": int(os.getenv("GAOBAO__VOICE__MAX_TOKENS") or tuning.get("max_tokens", 500)),
    }


def _deep_set(d: dict[str, Any], keys: list[str], value: Any) -> None:
    """Set a nested dict value by key path. Creates intermediate dicts as needed."""
    current = d
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Recursively merge override into base, preserving base values for missing keys."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _override_from_env(
    target: dict[str, Any],
    env_key: str,
    keys: list[str],
    cast: type,
) -> None:
    """Override a nested config value from an env var if set."""
    val = os.getenv(env_key, "")
    if val:
        try:
            _deep_set(target, keys, cast(val))
        except (ValueError, TypeError):
            pass
