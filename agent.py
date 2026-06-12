#!/usr/bin/env python3
"""
高考志愿顾问 Agent — 模型无关、支持实时搜索、结构化槽位采集。
Usage:
  python agent.py                    # 交互式对话
  python agent.py --model qwen-plus # 指定模型
  python agent.py --no-search        # 禁用搜索
"""
from __future__ import annotations

import os, sys, json, re, urllib.request, urllib.parse, urllib.error, time, logging
from datetime import datetime
from typing import Any
from openai import OpenAI
from logger import log

# 高考数据模块（数据库优先 + 百度搜索兜底）
try:
    from gaokao_data import (
        query_admission, format_admission_info,
        query_school_info, query_major_info, query_match_schools,
        query_subject_ranking, search_policy, get_db_stats,
        query_yi_fen_yi_duan, query_match_schools_v2,
        query_admission_trend,
        query_schools_by_major, format_schools_by_major,
    )
    HAS_DATA_MODULE = True
except ImportError:
    HAS_DATA_MODULE = False

# 质量控制模块：情绪检测
try:
    from quality.emotion_detector import detect_emotion, CRISIS_HOTLINES
    HAS_EMOTION_DETECTOR = True
except ImportError:
    HAS_EMOTION_DETECTOR = False

# 质量控制模块：交叉验证
try:
    from quality.cross_validator import cross_validate_admission
    HAS_CROSS_VALIDATOR = True
except ImportError:
    HAS_CROSS_VALIDATOR = False

# 质量控制模块：AI时代专业风险评估
try:
    from quality.ai_era_risk import get_risk_summary
    HAS_AI_RISK = True
except ImportError:
    HAS_AI_RISK = False

# 质量控制模块：决策启发式推荐
try:
    from quality.decision_framework import recommend_heuristics as df_recommend_heuristics
    HAS_DECISION_FRAMEWORK = True
except ImportError:
    HAS_DECISION_FRAMEWORK = False

# 质量控制模块：决策反模式检测
try:
    from quality.anti_pattern_checker import check_anti_patterns, should_rewrite as ap_should_rewrite
    HAS_ANTI_PATTERN_CHECKER = True
except ImportError:
    HAS_ANTI_PATTERN_CHECKER = False

# 质量控制模块：模型选择矩阵
try:
    from quality.model_selector import select_models, format_model_hint
    HAS_MODEL_SELECTOR = True
except ImportError:
    HAS_MODEL_SELECTOR = False

# 埋点模块
try:
    from analytics.tracker import EventTracker
    _tracker = EventTracker()
    HAS_TRACKER = True
except Exception:
    _tracker = None
    HAS_TRACKER = False

def read_clipboard():
    """读取 Windows 剪贴板文本（安全版本，限制长度）。"""
    MAX_CLIPBOARD_LEN = 2000
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
            data = win32clipboard.GetClipboardData(13)
            win32clipboard.CloseClipboard()
            if data and len(data) > MAX_CLIPBOARD_LEN:
                data = data[:MAX_CLIPBOARD_LEN] + f"...(截断，原文{len(data)}字)"
            return data
        win32clipboard.CloseClipboard()
    except Exception:
        pass
    return None

# ── 加载 .env 文件 ──────────────────────────────────
def load_dotenv(path):
    """简单的 .env 加载器，不依赖第三方库（安全加固版）。"""
    if not os.path.exists(path):
        return
    MAX_LINE_LEN = 512
    MAX_KEY_LEN = 128
    MAX_VAL_LEN = 256
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if len(line) > MAX_LINE_LEN:
                continue
            # 去掉 export 前缀
            if line.startswith("export "):
                line = line[7:].strip()
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if not key or len(key) > MAX_KEY_LEN or len(val) > MAX_VAL_LEN:
                continue
            # 去掉引号
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            # 校验 key 格式（只允许大写字母、数字、下划线）
            if not re.match(r'^[A-Z][A-Z0-9_]*$', key):
                continue
            if key not in os.environ:
                os.environ[key] = val

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

# ── 常见模型预设 ────────────────────────────────────
# 用户只需设置 LLM_PROVIDER，系统自动填充 base_url 和 model
PRESETS = {
    "deepseek":  {"base_url": "https://api.deepseek.com",    "model": "deepseek-chat"},
    "qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm":       {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "moonshot":  {"base_url": "https://api.moonshot.cn/v1",   "model": "moonshot-v1-8k"},
    "openai":    {"base_url": "https://api.openai.com/v1",    "model": "gpt-4o"},
    "ollama":    {"base_url": "http://localhost:11434/v1",    "model": "qwen2.5:7b"},
}

def resolve_config():
    """解析配置：支持 LLM_PROVIDER 快捷切换 或 手工指定三项。"""
    provider = os.getenv("LLM_PROVIDER", "").lower()
    enable_search = os.getenv("ENABLE_SEARCH", "true").lower() in ("true", "1", "yes")
    if provider in PRESETS:
        preset = PRESETS[provider]
        return {
            "base_url": os.getenv("LLM_BASE_URL", preset["base_url"]),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", preset["model"]),
            "max_tokens": None,  # 不限制回复长度，让模型自由发挥
            "temperature": 0.7,
            "enable_search": enable_search,
        }
    return {
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "max_tokens": None,  # 不限制回复长度，让模型自由发挥
        "temperature": 0.7,
        "enable_search": enable_search,
    }

CONFIG = resolve_config()
SEARCH_ENGINE = "https://www.baidu.com/s?wd="

# 默认数据年份：取最近一个完整年份（高考数据通常在当年9月后更新）
DATA_YEAR = datetime.now().year - 1

# 全国省级行政区（含台湾，共 32 个；单一数据源，消除重复）
PROVINCES = [
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
    "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
]
# 省份提取正则（编译一次，复用多次）
_PROVINCE_RE = re.compile(r'(' + '|'.join(PROVINCES) + r')')

# 3+3 高考模式省份（选科不限定物理/历史二选一）
PROVINCES_33 = {"浙江", "上海", "北京", "天津", "山东", "海南"}

# 3+3 省份全部 20 种选科组合（6选3 = C(6,3) = 20）
SUBJECT_COMBOS_33 = [
    "物化生", "物化政", "物化地", "物生政", "物生地", "物政地",
    "化生政", "化生地", "化政地", "生政地",
    "物化史", "物生史", "物政史", "物地史",
    "化生史", "化政史", "化地史",
    "生政史", "生地史",
    "政地史",
]
# 3+3 省份单科选考（用户可能只选了一科告知）
SUBJECT_SINGLE_33 = ["物理", "化学", "生物", "历史", "地理", "政治"]
# 3+3 组合简称 → 展开映射（如 "物化生" → "物理+化学+生物"）
_SUBJ_ABBR_MAP = {"物": "物理", "化": "化学", "生": "生物", "史": "历史", "地": "地理", "政": "政治"}
# 预编译 3+3 组合识别正则
_SUBJECT_COMBO_33_RE = re.compile(
    r'(物化生|物化政|物化地|物生政|物生地|物政地|'
    r'化生政|化生地|化政地|生政地|'
    r'物化史|物生史|物政史|物地史|'
    r'化生史|化政史|化地史|'
    r'生政史|生地史|政地史)'
)

# ── 加载知识库 ──────────────────────────────────────
KNOWLEDGE_BASE_PATH = os.path.join(HERE, "knowledge_base.md")
SYSTEM_PROMPT_PATH = os.path.join(HERE, "system_prompt.md")
QUOTES_INDEX_PATH = os.path.join(HERE, "knowledge", "quotes", "_by_major.json")

# 加载语录索引（用于按专业查询张雪峰语录）
def load_quotes_index():
    """加载语录的反向索引（专业→语录列表）"""
    if os.path.exists(QUOTES_INDEX_PATH):
        with open(QUOTES_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

QUOTES_INDEX = load_quotes_index()

def load_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ── 槽位管理器 ───────────────────────────────────────
SLOTS = {
    "province":     {"label": "省份", "filled": False, "value": ""},
    "score_rank":   {"label": "分数/位次", "filled": False, "value": ""},
    "subject":      {"label": "选科", "filled": False, "value": ""},
    "interest":     {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
    "region":       {"label": "地域偏好", "filled": False, "value": ""},
    "family":       {"label": "家庭资源", "filled": False, "value": ""},
    "goal":         {"label": "核心诉求", "filled": False, "value": ""},
}

def filled_slots(slots=None):
    s = slots if slots is not None else SLOTS
    return {k: v for k, v in s.items() if v["filled"]}

def missing_slots(slots=None):
    s = slots if slots is not None else SLOTS
    return [k for k, v in s.items() if not v["filled"]]

def slots_summary(slots=None):
    s = slots if slots is not None else SLOTS
    lines = []
    for k, v in s.items():
        status = "[OK]" if v["filled"] else "[ ]"
        lines.append(f"  {status} {v['label']}: {v['value'] if v['filled'] else '(未填)'}")
    return "\n".join(lines)

def _chinese_num_to_int(text: str) -> int | None:
    """将中文数字（如'五百八十'）转换为整数。支持到万位。"""
    digit_map = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
                 '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    unit_map = {'十': 10, '百': 100, '千': 1000, '万': 10000}
    if not text:
        return None
    result = 0
    current = 0
    wan_part = 0
    for ch in text:
        if ch in digit_map:
            current = digit_map[ch]
        elif ch in unit_map:
            u = unit_map[ch]
            if u == 10000:
                wan_part = (result + (current if current else 1)) * 10000
                result = 0
                current = 0
            else:
                if current == 0 and u == 10:
                    current = 1  # "十" 开头隐含 "一十"
                result += current * u
                current = 0
    result += current
    result += wan_part
    return result if result > 0 else None


def _expand_subject_combo(abbr: str) -> str:
    """将 3+3 选科简称展开为完整表述，如 '物化生' → '物理+化学+生物'。"""
    return "+".join(_SUBJ_ABBR_MAP.get(ch, ch) for ch in abbr)


def _parse_oral_score(msg: str) -> int | None:
    """解析口语化分数表达，如 '五百八'、'六百出头' → 整数分数。

    处理省略"十"的口语习惯：
      五百八 → 580（= 五百八十）
      六百一 → 610（= 六百一十）
      六百 → 600
    """
    digit_map = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
                 '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    # 匹配 "X百Y" 模式（Y 可选，省略"十"）
    m = re.search(r'([一二三四五六七八九两])百([一二三四五六七八九零])?(?:出头|左右)?', msg)
    if m:
        bai = digit_map.get(m.group(1), 0) * 100
        shi = digit_map.get(m.group(2), 0) * 10 if m.group(2) else 0
        val = bai + shi
        if 100 <= val <= 750:
            return val
    # 匹配 "X百" 纯百位
    m2 = re.search(r'([一二三四五六七八九两])百(?:出头|左右)?(?:\s|$|，|,|。)', msg)
    if m2:
        val = digit_map.get(m2.group(1), 0) * 100
        if 100 <= val <= 750:
            return val
    return None


def extract_slots_from_message(msg, slots=None):
    """从用户消息中自动提取槽位信息。支持一句话多槽位同时提取。"""
    s = slots if slots is not None else SLOTS
    updated = []

    # ── 省份检测（增强：支持方言暗示、"我是X人"、"X考生"、"在X考的"等）──
    # 方言→省份推测映射（仅在省份未确定时使用）
    _dialect_province_hints = {
        "俺": ["山东", "河南"],
        "阿拉": ["上海"],
        "咱": ["北京", "天津", "河北", "山东"],
        "额": ["陕西", "甘肃"],
        "额滴": ["陕西"],
        "咱家": ["北京", "天津", "河北", "山东"],
    }
    if not s["province"]["filled"]:
        province_context_re = re.compile(
            r'(?:在|到|去|来|我是|我家在|老家|籍贯|户籍)(?:的|了|位于|住在)?'
            r'?\s*(' + '|'.join(PROVINCES) + r')'
            r'|(' + '|'.join(PROVINCES) + r')(?:考生|的|人|高考|参加高考|读高中|上的学)'
        )
        m = province_context_re.search(msg)
        if m:
            prov = m.group(1) or m.group(2)
            if prov:
                s["province"]["value"] = prov
                s["province"]["filled"] = True
                updated.append(f"省份→{prov}")
        else:
            for p in PROVINCES:
                if p in msg:
                    s["province"]["value"] = p
                    s["province"]["filled"] = True
                    updated.append(f"省份→{p}")
                    break
            # 方言→省份推测（仅在无法直接匹配省份时触发）
            if not s["province"]["filled"]:
                for dialect, candidates in _dialect_province_hints.items():
                    if dialect in msg:
                        s["province"]["value"] = candidates[0]
                        s["province"]["filled"] = True
                        updated.append(f"省份→{candidates[0]}(方言推测)")
                        break

    # ── 分数/位次检测（增强版：数字分数、中文数字、一本线上N分）──
    score_match = None
    score_patterns = [
        r'(?:考了|高考|分数|成绩|总分)?\s*(\d{3})\s*分',
        r'(?:考了|高考|成绩|总分)\s*(\d{3})(?:\s|$|，|,|。|！)',
        r'(\d{3})\s*分',
    ]
    for sp in score_patterns:
        m = re.search(sp, msg)
        if m:
            score_match = m
            break

    # 中文数字分数：五百八十分 / 六百分
    cn_score_match = None
    if not score_match:
        cn_re = re.search(r'([一-鿿]{2,6})\s*分', msg)
        if cn_re:
            cn_num = _chinese_num_to_int(cn_re.group(1))
            if cn_num and 100 <= cn_num <= 750:
                cn_score_match = cn_num

    # 口语化中文数字（不带"分"字）：五百八、六百出头
    oral_score_match = None
    if not score_match and not cn_score_match:
        oral_score_match = _parse_oral_score(msg)

    # "差一本线N分"、"过了本科线N分"、"不到600"
    delta_line_match = None
    if not score_match and not cn_score_match and not oral_score_match:
        delta_patterns = [
            (r'差一本线\s*(\d{1,3})\s*分', "低于一本线{0}分"),
            (r'差特殊线\s*(\d{1,3})\s*分', "低于特殊线{0}分"),
            (r'(?:过了|超[过了]?|高[过了]?)(?:一本线|本科线|特殊线)\s*(\d{1,3})\s*分', "高于一本线{0}分"),
            (r'不到\s*(\d{3})', "<{0}分"),
            (r'没到\s*(\d{3})', "<{0}分"),
        ]
        for pat, fmt in delta_patterns:
            m = re.search(pat, msg)
            if m:
                delta_line_match = fmt.format(m.group(1))
                break

    # 一本线/特殊线上 N 分
    line_score_match = None
    if not score_match and not cn_score_match and not oral_score_match and not delta_line_match:
        line_re = re.search(r'一本线[上超多+]\s*(\d{1,3})\s*分?', msg)
        if not line_re:
            line_re = re.search(r'特殊线[上超多+]\s*(\d{1,3})\s*分?', msg)
        if line_re:
            line_score_match = f"一本线上{line_re.group(1)}分"

    # 多种位次格式（增加"全省第N名"）
    rank_patterns = [
        r'(\d{4,7})\s*(?:位次|名次|排名|名)',
        r'位次[是为：:\s]*(\d{4,7})',
        r'省排[名]?\s*(\d{4,7})',
        r'全省第\s*(\d{4,7})\s*名',
        r'(\d+(?:\.\d+)?)\s*万\s*(?:位次|名|名次)',
    ]
    rank_value = None
    for rp in rank_patterns:
        m = re.search(rp, msg)
        if m:
            raw = m.group(1)
            if '万' in rp and '.' in raw:
                rank_value = str(int(float(raw) * 10000))
            elif '万' in rp:
                rank_value = str(int(raw) * 10000)
            else:
                rank_value = raw
            break

    if score_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = score_match.group(1) + "分"
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{score_match.group(1)}分")
    elif cn_score_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = str(cn_score_match) + "分"
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{cn_score_match}分")
    elif oral_score_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = str(oral_score_match) + "分"
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{oral_score_match}分")
    elif delta_line_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = delta_line_match
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{delta_line_match}")
    elif line_score_match and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = line_score_match
        s["score_rank"]["filled"] = True
        updated.append(f"分数→{line_score_match}")
    if rank_value and not s["score_rank"]["filled"]:
        s["score_rank"]["value"] = "位次" + rank_value
        s["score_rank"]["filled"] = True
        updated.append(f"位次→{rank_value}")
    if rank_value and s["score_rank"]["filled"] and "位次" not in s["score_rank"]["value"]:
        s["score_rank"]["value"] += " / 位次" + rank_value

    # ── 选科检测（完整 3+1+2 全部12种组合 + 3+3 全部20种组合 + 自然表达）──
    if not s["subject"]["filled"]:
        # 3+1+2 组合（12种）+ 3+3 扩展组合（20种）+ 文理
        subject_combos = [
            # 3+1+2 原有12种
            "物化生", "物化地", "物化政", "物生政", "物生地", "物政地",
            "史政地", "史政生", "史地生", "史化生", "史化政", "史化地",
            "理科", "文科",
        ]
        # 3+3 扩展组合（去除已包含的）
        _existing = set(subject_combos)
        for combo in SUBJECT_COMBOS_33:
            if combo not in _existing:
                subject_combos.append(combo)
        # 常见排列变体（学生可能用不同的字序，如 "政史地" = "史政地"）
        _perm_variants = [
            "政史地", "政地史", "地政史", "地史政", "史地政",
            "生物化", "化生物", "生物物", "生化物",
            "物政生", "政物生", "政物化", "物政化",
            "地物化", "地化物",
        ]
        for v in _perm_variants:
            if v not in _existing:
                subject_combos.append(v)
                _existing.add(v)

        matched_subj = None
        for subj in subject_combos:
            if subj in msg:
                matched_subj = subj
                break

        # 3+3 自然表达解析："选了物理化学地理" / "选考政治历史生物"
        if not matched_subj:
            _all_subject_names = "|".join(SUBJECT_SINGLE_33)
            natural_33_re = re.search(
                r'(?:选[的了考]?|选考)\s*(' + _all_subject_names + r')\s*'
                r'(' + _all_subject_names + r')?\s*'
                r'(' + _all_subject_names + r')?',
                msg
            )
            if natural_33_re:
                parts = [natural_33_re.group(i) for i in (1, 2, 3) if natural_33_re.group(i)]
                if len(parts) >= 2:
                    matched_subj = "+".join(parts)

        # 自然表达："选的物理"、"物理方向"、"选的化学"（3+3支持6科单选）
        if not matched_subj:
            _single_33 = "|".join(SUBJECT_SINGLE_33)
            subj_natural_re = re.search(
                r'(?:选[的了]?|学[的了]?|考[的了]?|方向)\s*(' + _single_33 + r')',
                msg
            )
            if subj_natural_re:
                matched_subj = subj_natural_re.group(1)
        # 裸关键词（扩展为6科，支持 3+3 省份单科选考）
        if not matched_subj:
            for subj in SUBJECT_SINGLE_33:
                if subj in msg:
                    matched_subj = subj
                    break
        if matched_subj:
            s["subject"]["value"] = matched_subj
            s["subject"]["filled"] = True
            updated.append(f"选科→{matched_subj}")

    # ── 地域检测（扩展城市列表）──
    for r in ["省内", "本省", "离家近", "北上广", "江浙沪", "北京", "上海",
               "深圳", "广州", "杭州", "成都", "武汉", "南京", "西安",
               "天津", "重庆", "长沙", "合肥", "济南", "郑州", "昆明",
               "厦门", "苏州", "无锡", "佛山", "东莞"]:
        if r in msg and not s["region"]["filled"]:
            s["region"]["value"] = r
            s["region"]["filled"] = True
            updated.append(f"地域→{r}")
            break

    # ── 家庭资源检测 ──
    for fw in ["电力", "电网", "铁路", "医生", "教师", "老师", "做生意",
                "公务员", "烟草", "石油", "普通家庭", "没资源",
                "经济一般", "经济压力大", "条件一般", "家里没钱", "没钱",
                "能负担", "能接受高学费", "私立", "中外合作"]:
        if fw in msg and not s["family"]["filled"]:
            s["family"]["value"] = fw
            s["family"]["filled"] = True
            updated.append(f"家庭→{fw}")
            break

    # ── 诉求检测（增强：更多自然表达）──
    if not s["goal"]["filled"]:
        goal_patterns = [
            (r'(?:想|要|打算|希望|注重|看重|追求|主要)[^，。]*?(?:稳定|安稳|铁饭碗)', "稳定"),
            (r'(?:想|要|打算|希望|注重|看重|追求|主要)[^，。]*?(?:考公|公务员|体制内|进体制)', "考公"),
            (r'(?:想|要|打算|希望)[^，。]*?(?:考研|读研|深造|学术)', "考研"),
            (r'(?:想|要|打算|希望|注重|看重|追求|主要)[^，。]*?(?:就业|找工作|工作)', "就业"),
            (r'(?:想|要|希望|追求)[^，。]*?(?:赚钱|高薪|高收入|搞钱)', "高薪"),
            (r'(?:想|打算|希望)[^，。]*?(?:出国|留学)', "出国"),
            (r'(就业|考公|考研|稳定|高薪|赚钱|深造|出国)', None),
        ]
        for pattern, goal_val in goal_patterns:
            m = re.search(pattern, msg)
            if m:
                s["goal"]["value"] = goal_val if goal_val else m.group(1)
                s["goal"]["filled"] = True
                updated.append(f"诉求→{s['goal']['value']}")
                break

    # ── 兴趣/厌恶检测（增强：自然表达解析）──
    if not s["interest"]["filled"]:
        _major_names = (
            r'计算机|软件|人工智能|AI|电气|电子信息|通信|'
            r'临床医学|口腔|金融|会计|法学|土木|机械|'
            r'新闻|汉语言|数学|物理|化学|生物|材料|'
            r'环境|自动化|集成电路|大数据|信息安全|车辆|'
            r'建筑学|统计学|药学|师范|英语|历史学|哲学|'
            r'工科|理科|文科|医学|管理'
        )
        # 负面兴趣必须先检查（"不想学"包含"想学"子串，正面会误匹配）
        interest_negative_re = re.search(
            r'(?:不想学|讨厌|不喜欢|不想[做干读]|绝不学|绝对不|抗拒|排斥)'
            r'.*?(' + _major_names + r')',
            msg
        )
        # 正面兴趣：想学X / 喜欢X / 感兴趣 / 以后想干X
        interest_positive_re = None
        if not interest_negative_re:
            interest_positive_re = re.search(
                r'(?:想学|想读|喜欢|感兴趣|对.{0,4}有兴趣|想从事|以后想[做干]|选.{0,2}专业)'
                r'.*?(' + _major_names + r')',
                msg
            )
        if interest_negative_re:
            val = interest_negative_re.group(1)
            s["interest"]["value"] = f"不想学{val}"
            s["interest"]["filled"] = True
            updated.append(f"兴趣→不想学{val}")
        elif interest_positive_re:
            val = interest_positive_re.group(1)
            s["interest"]["value"] = f"想学{val}"
            s["interest"]["filled"] = True
            updated.append(f"兴趣→想学{val}")
        else:
            # 原有关键词列表兜底
            interest_keywords = [
                "计算机", "软件", "人工智能", "AI", "电气", "电子信息", "通信",
                "临床医学", "口腔", "金融", "会计", "法学", "土木", "机械",
                "新闻", "汉语言", "数学", "物理", "化学", "生物", "材料",
                "环境", "自动化", "集成电路", "大数据", "信息安全", "车辆",
                "建筑学", "统计学", "药学", "师范", "英语", "历史学", "哲学",
                "想学", "喜欢", "想读", "感兴趣", "讨厌", "不想学", "不喜欢",
                "绝对不", "绝不",
            ]
            matched_interests = [kw for kw in interest_keywords if kw in msg]
            if matched_interests:
                s["interest"]["value"] = " ".join(matched_interests[:3])
                s["interest"]["filled"] = True
                updated.append(f"兴趣→{'、'.join(matched_interests[:3])}")

    return updated

def is_consultation_intent(msg):
    """判断用户是否有志愿咨询意图。"""
    keywords = [
        "高考", "志愿", "选专业", "报学校", "报志愿", "填志愿", "选科",
        "分科", "考研", "选学校", "大学", "专业", "就业", "考公",
        "能报", "能上", "推荐", "建议", "帮忙看", "帮我选",
    ]
    return any(kw in msg for kw in keywords)

# ── 搜索功能 ─────────────────────────────────────────
# SSRF 防御: 禁止访问的内网/危险IP段
_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254",
    "metadata.google.internal", "100.100.100.200",
}

def _is_safe_url(url: str) -> bool:
    """检查URL是否安全（防SSRF）：拒绝内网地址和非HTTP协议。"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if hostname in _BLOCKED_HOSTS:
            return False
        # 拒绝内网IP段
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # hostname 不是IP（正常域名），继续检查
            pass
        # 拒绝常见内网域名后缀
        for suffix in (".local", ".internal", ".localhost", ".lan"):
            if hostname.endswith(suffix):
                return False
        return True
    except Exception:
        return False


def _sanitize_html(text: str) -> str:
    """强化HTML清理，防止XSS残留（#6）。委托给 utils.sanitize_html。"""
    from utils import sanitize_html
    return sanitize_html(text)


def web_search(query, max_results=3):
    """搜索并获取网页内容。先用百度搜索找URL，再抓取页面文字。（安全加固版）"""
    results = []
    try:
        # Step 1: 百度搜索获取结果链接
        url = SEARCH_ENGINE + urllib.parse.quote(query[:200])  # 限制查询长度
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Step 2: 提取搜索结果URL（尝试多种匹配模式）
        urls = re.findall(r'href="(https?://[^"]+)"', html)
        # 过滤掉百度自己的链接，保留真实网站
        valid_urls = [u for u in urls if 'baidu.com' not in u and len(u) > 30][:max_results]

        # Step 3: 抓取每个结果页面的文字内容（SSRF 防御）
        for target_url in valid_urls:
            # SSRF 防御: 校验 URL 安全性
            if not _is_safe_url(target_url):
                continue
            try:
                page_req = urllib.request.Request(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(page_req, timeout=8) as page_resp:
                    # 防御: 限制下载大小（最大 512KB）
                    content = page_resp.read(512 * 1024)
                    page_html = content.decode("utf-8", errors="ignore")
                # XSS 防御: 强化 HTML 清理
                clean = _sanitize_html(page_html)
                # 取有效内容（100-500字）
                if len(clean) > 100:
                    results.append(clean[:500] + "...")
            except Exception:
                continue

        if not results:
            # Step 4: 降级——只取百度摘要
            snippets = re.findall(r'<span class="content-right_[^"]*">(.*?)</span>', html)
            for s in snippets[:max_results]:
                clean = _sanitize_html(s)
                if len(clean) > 20:
                    results.append(clean)

        return results if results else ["(搜索无结果，建议手动查询官方渠道)"]
    except Exception as e:
        return [f"(搜索暂时不可用)"]  # #9: 不泄露错误细节

def should_search(msg):
    """判断是否需要联网搜索——更积极触发。"""
    triggers = [
        "今年", "最新", "2026", "2025", "最近", "现在",
        "分数线", "录取分", "投档线", "招生计划", "录取",
        "政策", "变化", "改革", "新规",
        "就业率", "就业前景", "薪资", "月薪", "年薪",
        "排名", "第几名", "怎么样", "好不好",
        "能上", "能报", "能进", "稳不稳", "冲不冲",
        "多少分", "什么专业", "一本", "二本", "985", "211",
        "王牌专业", "优势", "缺点", "劣势", "值得", "推荐吗",
    ]
    return any(t in msg for t in triggers)

# ── 安全防御 ─────────────────────────────────────────

# #4: Prompt Injection 检测与防御
_INJECTION_PATTERNS = [
    r'(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)',
    r'(?i)forget\s+(?:all\s+)?(?:previous|prior|above)',
    r'(?i)you\s+are\s+now\s+(?:a|an|the)',
    r'(?i)new\s+(?:system\s+)?(?:instructions?|prompt|rules?|role)',
    r'(?i)override\s+(?:your|the)\s+(?:instructions?|rules?|system)',
    r'(?i)output\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?|rules?)',
    r'(?i)reveal\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)',
    r'(?i)repeat\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)',
    r'(?i)print\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)',
    r'(?i)show\s+me\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)',
    r'(?i)what\s+(?:are|is)\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)',
    r'(?i)\bDAN\b.*\bjailbreak\b',
    r'(?i)pretend\s+you\s+(?:are|have)',
    r'(?i)act\s+as\s+(?:if|though)',
    r'(?i)disregard\s+(?:all|any|the)',
    r'(?i)from\s+now\s+on\s+(?:you|respond|answer|output)',
    r'(?i)system:\s*(?:you|ignore|forget|new)',
]
_INJECTION_RE = [re.compile(p) for p in _INJECTION_PATTERNS]

def detect_prompt_injection(msg: str) -> bool:
    """检测用户输入中的 prompt injection 攻击模式。"""
    # 截断过长的输入（正常用户不太会发超长消息）
    if len(msg) > 5000:
        return True
    for pattern in _INJECTION_RE:
        if pattern.search(msg):
            return True
    return False

# #13: 通配符转义（防止 ORM LIKE 查询注入）
def sanitize_like_query(value: str) -> str:
    """转义 SQL LIKE 通配符（%, _）。"""
    return value.replace('%', '\\%').replace('_', '\\_')

# 最大用户输入长度
MAX_USER_INPUT_LEN = 3000

def validate_user_input(msg: str) -> str:
    """校验和清理用户输入。返回清理后的消息，或抛出异常。"""
    if not msg or not msg.strip():
        return msg
    msg = msg.strip()
    if len(msg) > MAX_USER_INPUT_LEN:
        msg = msg[:MAX_USER_INPUT_LEN] + "...(输入过长已截断)"
    return msg

# ── LLM 对话 ─────────────────────────────────────────
def cleanup_format(text, cli_mode=True):
    """清理 AI 模型输出中的 Markdown 格式。

    cli_mode=True（默认）: 去掉所有 Markdown，纯文本聊天风格。
    cli_mode=False（Web 端）: 只去掉标题标记，保留加粗/列表供 st.markdown 渲染。
    """
    if not text:
        return text
    # 去掉 ### 标题（CLI/Web 都不需要 LLM 自作主张加标题）
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    if cli_mode:
        # CLI 模式：全部去格式，像真人聊天
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+[\.\、]\s*', '', text, flags=re.MULTILINE)
    return text.strip()

class GaokaoAdvisor:
    """高考志愿 AI 顾问核心类。

    Attributes:
        model: 当前使用的 LLM 模型名。
        slots: 用户信息槽位（省份/分数/选科/兴趣/地域/家庭/诉求）。
        cli_mode: True=CLI纯文本输出 / False=Web保留Markdown格式。
        conversation: 对话历史（最多保留 MAX_HISTORY 条）。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        slots: dict[str, dict[str, Any]] | None = None,
        cli_mode: bool = False,
    ) -> None:
        # 支持外部传入 API 配置（多用户场景各自用自己的 key）
        _api_key = api_key or CONFIG["api_key"]
        _base_url = base_url or CONFIG["base_url"]
        _model = model or CONFIG["model"]
        self.model = _model
        self.client = OpenAI(base_url=_base_url, api_key=_api_key)
        self.knowledge_base = load_file(KNOWLEDGE_BASE_PATH)
        self.system_prompt = load_file(SYSTEM_PROMPT_PATH)
        self.conversation = []
        self.cli_mode = cli_mode  # True=CLI纯文本 / False=Web保留Markdown
        # 支持外部传入独立的 slots（多用户场景各自有自己的槽位）
        self.slots = slots if slots is not None else {k: dict(v) for k, v in SLOTS.items()}
        # #18: 系统消息缓存（避免每轮重新构建巨大的 system message）
        self._cached_base_system = None  # 不含槽位和搜索状态的基础部分
        self._cache_dirty = True

    def _build_system_message(self):
        """构建系统消息，包含 system prompt + 知识库 + 数据库状态 + 数据治理规则 + 槽位状态。"""
        kb = self.knowledge_base if self.knowledge_base else ""
        slots_status = slots_summary(self.slots)
        search_note = ""
        if CONFIG["enable_search"]:
            search_note = "\n\n【联网搜索已启用。遇到最新政策/分数线/就业数据等问题时，优先查询本地数据库，数据不足时再搜索。】"

        # 数据库状态
        db_info = ""
        if HAS_DATA_MODULE:
            try:
                stats = get_db_stats()
                if isinstance(stats, dict) and "schools" in stats:
                    db_info = f"""
【本地数据库已就绪】
- 院校: {stats['schools']} 条（985/211/双一流/普通）
- 专业: {stats['majors']} 条（含就业率、薪资、就业方向）
- 录取分数线: {stats['admission_scores']} 条（多省份多年份）
- 学科排名: {stats['subject_rankings']} 条（教育部评估）
- 招生政策: {stats['policies']} 条

数据来源：官方数据（教育部/省考试院）> 权威平台（掌上高考/麦可思）> 百度搜索（仅供参考）
**引用录取分数/就业数据时必须标注数据来源和具体年份**（如「20XX年数据显示...」）。"""
            except Exception:
                db_info = "\n【本地数据库加载中...】"

        full_system = f"""{self.system_prompt}
{db_info}
{search_note}

【知识库参考】
{kb}

【当前用户信息采集状态】
{slots_status}

【数据查询规则】
当用户问到具体学校/专业/分数时，按以下优先级获取数据：
1. 本地数据库（有结构化的录取分数、院校信息、专业就业数据）→ 直接引用并标注来源
2. 百度实时搜索（数据库没有时的兜底方案）→ 标注"百度搜索，仅供参考，请核实官方数据"
3. 用户自行查询（数据完全缺失时）→ 建议去省考试院官网/阳光高考平台查询

严禁编造具体的录取分数和位次。不确定的数据必须标注"请核实"。

请在回答时：
1. 如果用户信息不全，追问缺失的槽位（用自然的方式，不要像填表）。
2. 如果信息已经足够（至少省份+分数/位次+核心诉求），查询数据库获取匹配院校后给出冲稳保推荐。
3. 引用数据时标注来源（如"根据教育部2023年学科评估..."或"数据库显示该校2024年录取线..."）。
4. 保持直爽、接地气的风格。"""

        # 3+3 省份专项适配提示
        prov_val = self.slots.get("province", {}).get("value", "")
        if prov_val in PROVINCES_33:
            full_system += """

【3+3 省份专项适配】
该省份采用 3+3 模式，选科组合有 20 种，不限定物理/历史二选一。
推荐时注意：部分专业对选考科目有特定要求（如临床医学要求物理+化学，计算机类要求物理等）。
3+3 省份的录取数据通常以"3+3综合"为科类标识，而非"物理类/历史类"。"""

        return full_system

    # ── 子方法：注入选科匹配信息 ──
    def _inject_subject_compatibility(self, messages: list, user_msg: str) -> None:
        """选科匹配检查：仅在咨询意图且用户提供了选科时注入。"""
        if not (HAS_DATA_MODULE and self.slots.get("subject", {}).get("filled") and is_consultation_intent(user_msg)):
            return
        try:
            from gaokao_data import check_user_subject_compatibility, format_subject_compatibility
            user_subj_text = self.slots["subject"]["value"]
            _known_subjects = ["物理", "历史", "化学", "生物", "政治", "地理"]
            user_subj_list = [s for s in _known_subjects if s in user_subj_text]
            if user_subj_list:
                compat_result = check_user_subject_compatibility(user_subj_list)
                subj_hint = format_subject_compatibility(compat_result)
                messages.append({"role": "system", "content": subj_hint})
        except Exception as e:
            logging.warning("选科匹配注入失败: %s", e)

    # ── 子方法：注入张雪峰语录 ──
    def _inject_quotes(self, messages: list, user_msg: str) -> None:
        """根据用户提到的专业，注入相关语录作为参考。"""
        if not QUOTES_INDEX:
            return
        quote_keywords = [mk for mk in QUOTES_INDEX if mk in user_msg]
        if not quote_keywords:
            return
        quotes_to_inject = []
        for mk in quote_keywords[:2]:  # 最多注入 2 个专业的语录
            for q in QUOTES_INDEX[mk][:2]:  # 每专业最多 2 条
                quotes_to_inject.append(q["text"])
        if quotes_to_inject:
            quote_text = "\n".join([f"· {q}" for q in quotes_to_inject[:3]])
            messages.append({
                "role": "system",
                "content": f"【相关语录参考】\n{quote_text}\n（以上语录可化用到回复中，不要一字不差照搬）"
            })

    # ── 子方法：查询数据（数据库 + 搜索） ──
    def _query_data_hints(self, user_msg: str) -> list:
        """从数据库和搜索引擎获取结构化数据提示。返回 data_hints 列表。"""
        if not (CONFIG["enable_search"] and should_search(user_msg)):
            return []

        data_hints = []
        school_match = re.findall(r'[一-鿿]{2,10}(?:大学|学院|学校)', user_msg)
        prov_match = _PROVINCE_RE.findall(user_msg)

        if not HAS_DATA_MODULE:
            # 数据库不可用，直接走百度搜索
            return self._fallback_web_search(user_msg)

        # 1. 查录取分数线（学校+省份）+ 交叉验证
        if school_match and prov_match:
            try:
                raw = query_admission(school_match[0], prov_match[0])
                if raw:
                    conf_tag = ""
                    if HAS_CROSS_VALIDATOR and len(raw) >= 2:
                        validation_sources = []
                        for r in raw:
                            if r.get("min_score") is not None:
                                validation_sources.append({
                                    "source": r.get("data_source", "未知")[:15],
                                    "min_score": r["min_score"],
                                    "min_rank": r.get("min_rank"),
                                })
                        if len(validation_sources) >= 2:
                            cv = cross_validate_admission(validation_sources)
                            if cv:
                                conf_tag = f" [置信度:{cv['confidence']}]"
                                if cv["note"]:
                                    conf_tag += f" {cv['note']}"
                    admission_text = format_admission_info(raw)
                    if admission_text and "暂无" not in admission_text:
                        # 注入数据置信度分数
                        conf_scores = [r.get("confidence_score", 0) for r in raw if r.get("confidence_score")]
                        data_tiers = set(r.get("data_tier", "") for r in raw if r.get("data_tier"))
                        score_tag = ""
                        if conf_scores:
                            avg_score = sum(conf_scores) // len(conf_scores)
                            tier_label = {"T1": "本地数据库", "T2": "百度高考API", "T3": "百度搜索"}
                            tier_names = "/".join(tier_label.get(t, t) for t in data_tiers if t)
                            score_tag = f" [数据置信度:{avg_score}分 来源:{tier_names}]"
                        data_hints.append(f"【录取数据查询结果】{conf_tag}{score_tag}\n{admission_text}")
            except Exception as e:
                logging.warning("data_hints 查询失败: %s", e)

        # 2. 查院校基本信息
        if school_match:
            try:
                info = query_school_info(school_match[0])
                if info:
                    level_parts = []
                    if info.get("is_985"): level_parts.append("985")
                    if info.get("is_211"): level_parts.append("211")
                    if info.get("is_double_first_class"): level_parts.append("双一流")
                    level_str = "/".join(level_parts) if level_parts else info.get("level", "")
                    data_hints.append(
                        f"【院校信息】{info['name']} | {info['province']}{info['city']} | "
                        f"{level_str} {info.get('school_type','')} | 软科排名{info.get('ranking','未知')} | "
                        f"来源：{info['data_source']}"
                    )
            except Exception as e:
                logging.warning("data_hints 查询失败: %s", e)

        # 3. 提取专业关键词，查就业数据
        major_match = re.findall(
            r'(计算机|软件|人工智能|电气|电子信息|通信|临床医学|口腔|金融|法学|会计|土木|机械|新闻|汉语言|数学|物理|化学|生物|材料|环境|自动化|集成电路|大数据|物联网|信息安全|车辆工程|建筑学|统计学|药学|师范|英语|历史学|哲学)',
            user_msg
        )
        if major_match:
            try:
                major_info = query_major_info(major_match[0])
                if major_info:
                    emp_rate = f"{major_info['employment_rate']*100:.0f}%" if major_info.get('employment_rate') else "未知"
                    salary = f"{major_info['avg_salary']:.0f}元/月" if major_info.get('avg_salary') else "未知"
                    data_hints.append(
                        f"【就业数据】{major_info['name']} | {major_info.get('category','')} | "
                        f"就业率{emp_rate} | 毕业5年均薪{salary} | "
                        f"来源：{major_info['data_source']}"
                    )
            except Exception as e:
                logging.warning("data_hints 查询失败: %s", e)

            # 附加 AI 时代专业风险评估
            if HAS_AI_RISK:
                for mj in major_match[:2]:
                    risk_summary = get_risk_summary(mj)
                    if risk_summary:
                        data_hints.append(f"【AI时代风险评估】{risk_summary}")
                        break

        # 4. 对比模式检测（P2-1）：A和B哪个好 / A vs B / A好还是B好
        contrast_match = re.search(
            r'([一-龥]{2,10}(?:大学|学院|学校))\s*[和跟与vVsS]{1,3}\s*([一-龥]{2,10}(?:大学|学院|学校))',
            user_msg,
        )
        if not contrast_match:
            # 尝试单校 + 对比关键词模式
            all_schools_in_msg = re.findall(r'[一-龥]{2,10}(?:大学|学院|学校)', user_msg)
            if len(all_schools_in_msg) >= 2 and re.search(r'(?:好还是|还是|哪个好|选哪个|对比)', user_msg):
                contrast_match = type('Match', (), {
                    'group': lambda self, n: all_schools_in_msg[n - 1]
                })()

        if contrast_match:
            try:
                school_a = contrast_match.group(1)
                school_b = contrast_match.group(2)
                prov = prov_match[0] if prov_match else "全国"
                subject = "物理类" if "物理" in user_msg else ("历史类" if "历史" in user_msg else "综合")

                contrast_parts = [f"【对比分析】{school_a} vs {school_b}（{prov}）"]

                # 并行查询两校数据
                for name in [school_a, school_b]:
                    try:
                        adm = query_admission(name, prov)
                        if adm:
                            contrast_parts.append(f"\n▸ {name} 录取数据:\n{format_admission_info(adm[:3])}")
                    except Exception:
                        pass
                    try:
                        info = query_school_info(name)
                        if info:
                            level_parts = []
                            if info.get("is_985"): level_parts.append("985")
                            if info.get("is_211"): level_parts.append("211")
                            if info.get("is_double_first_class"): level_parts.append("双一流")
                            level_str = "/".join(level_parts) if level_parts else info.get("level", "")
                            contrast_parts.append(
                                f"  院校属性: {level_str} | {info.get('school_type','')} | "
                                f"排名{info.get('ranking','未知')}"
                            )
                    except Exception:
                        pass

                # 查询历年趋势（P2-3 联动）
                for name in [school_a, school_b]:
                    try:
                        trend = query_admission_trend(name, prov, subject)
                        if trend and trend["trend"] != "数据不足":
                            contrast_parts.append(f"\n▸ {name} 趋势: {trend['trend_detail']}")
                    except Exception:
                        pass

                data_hints.append("\n".join(contrast_parts))
            except Exception as e:
                logging.warning("对比模式查询失败: %s", e)

        # 5. 历年趋势分析（P2-3）：用户提到"趋势""变化""近几年"时触发
        trend_keywords = ["趋势", "变化", "近几年", "历年", "近年", "波动", "涨了", "降了", "涨分", "降分"]
        if any(kw in user_msg for kw in trend_keywords) and school_match:
            try:
                prov = prov_match[0] if prov_match else "全国"
                subject = "物理类" if "物理" in user_msg else ("历史类" if "历史" in user_msg else "综合")
                for sname in school_match[:2]:
                    trend = query_admission_trend(sname, prov, subject)
                    if trend:
                        lines = [f"【历年趋势】{trend['school']}（{trend['province']} {trend['subject_type']}）"]
                        if trend["data"]:
                            for d in trend["data"]:
                                score_str = f"最低分{d['min_score']}" if d.get("min_score") else "暂无分数"
                                rank_str = f"位次{d['min_rank']}" if d.get("min_rank") else ""
                                lines.append(f"  {d['year']}年: {score_str} {rank_str}")
                        lines.append(f"  趋势判断: {trend['trend_detail']}")
                        data_hints.append("\n".join(lines))
            except Exception as e:
                logging.warning("趋势分析注入失败: %s", e)

        # 6. 专业百科卡片（P2-6）：检测到专业关键词时注入百科信息
        major_keywords = [
            "计算机", "软件", "人工智能", "电气", "电子信息", "通信",
            "临床医学", "口腔", "金融", "法学", "会计", "土木", "机械",
            "新闻", "汉语言", "数学", "物理", "化学", "生物", "材料",
            "环境", "自动化", "集成电路", "大数据", "物联网", "信息安全",
            "车辆工程", "建筑学", "统计学", "药学", "师范", "英语",
            "历史学", "哲学",
        ]
        major百科_hits = [mk for mk in major_keywords if mk in user_msg]
        if major百科_hits and HAS_DATA_MODULE:
            try:
                from gaokao_data import query_major_info as _qmi
                for mj_name in major百科_hits[:2]:
                    mj = _qmi(mj_name)
                    if mj:
                        emp_rate = f"{mj['employment_rate']*100:.0f}%" if mj.get('employment_rate') else "未知"
                        salary = f"{mj['avg_salary']:.0f}" if mj.get('avg_salary') else "未知"
                        postgrad = f"{mj['postgraduate_rate']*100:.0f}%" if mj.get('postgraduate_rate') else "未知"
                        card = (
                            f"【专业百科】{mj['name']} | "
                            f"学科门类:{mj.get('category','未知')} | "
                            f"专业类:{mj.get('sub_category','未知')} | "
                            f"就业率:{emp_rate} | "
                            f"均薪:{salary}元/月 | "
                            f"考研率:{postgrad}"
                        )
                        if mj.get('job_directions'):
                            try:
                                directions = json.loads(mj['job_directions']) if isinstance(mj['job_directions'], str) else mj['job_directions']
                                if directions:
                                    card += f" | 就业方向:{','.join(directions[:5])}"
                            except Exception:
                                pass
                        if mj.get('description'):
                            card += f"\n简介: {mj['description'][:200]}"
                        data_hints.append(card)
            except Exception as e:
                logging.warning("专业百科卡片注入失败: %s", e)

        # 7. 专业→院校反查（P1-6）：检测"学XX""读XX专业""XX专业能上什么学校"等模式
        _major_first_patterns = [
            r'想学(?:习)?(.{2,10}?)(?:专业的?)?(?:能上|可以报|有什么|去哪|哪些)',
            r'读(.{2,10}?)(?:专业?)?(?:能上|可以报|有什么|去哪)',
            r'(.{2,10}?)(?:专业?)?能上什么学校',
            r'(.{2,10}?)(?:专业?)?(?:有哪些|有什么)学校',
            r'(.{2,10}?)(?:专业?)?(?:推荐|推荐什么)学校',
            r'(?:喜欢|想报|想读)(.{2,10}?)(?:，|,|\s)',
        ]
        _major_first_name = None
        for _pat in _major_first_patterns:
            _m = re.search(_pat, user_msg)
            if _m:
                _candidate = _m.group(1).strip()
                # 过滤掉太短或明显不是专业的词
                if len(_candidate) >= 2 and _candidate not in ("什么", "哪个", "哪里", "怎么", "如何"):
                    _major_first_name = _candidate
                    break

        if _major_first_name and prov_match and score_match and HAS_DATA_MODULE:
            try:
                subj = "物理类" if "物理" in user_msg else ("历史类" if "历史" in user_msg else "综合")
                major_result = query_schools_by_major(
                    _major_first_name, prov_match[0],
                    int(score_match.group(1)), subj, year=DATA_YEAR,
                )
                if major_result and major_result.get("total", 0) > 0:
                    major_hint = format_schools_by_major(major_result)
                    data_hints.append(f"【专业→院校反查】\n{major_hint}")
                    # 标记已做过专业反查，避免位次法重复推荐
                    self._major_reverse_done = True
                else:
                    data_hints.append(
                        f"【专业反查】暂未在数据库中找到「{_major_first_name}」专业在"
                        f"{prov_match[0]}的匹配院校招生计划。建议查询省考试院招生目录确认。"
                    )
            except Exception as e:
                logging.warning("专业→院校反查失败: %s", e)

        # 8. 如果有分数+省份+选科信息，做位次法匹配推荐
        score_match = re.search(r'(\d{3})\s*分', user_msg)
        if score_match and prov_match and not school_match and not getattr(self, '_major_reverse_done', False):
            data_hints.extend(self._query_rank_recommendations(
                int(score_match.group(1)), prov_match[0], user_msg
            ))
        # 清除标记
        self._major_reverse_done = False

        # 数据库没有足够数据 → 百度搜索兜底
        if not data_hints:
            data_hints.extend(self._fallback_web_search(user_msg))

        return data_hints

    # ── 子方法：位次法推荐 ──
    def _query_rank_recommendations(self, score: int, province: str, user_msg: str) -> list:
        """基于位次法的冲/稳/保推荐。"""
        hints = []
        try:
            subject = "物理类" if "物理" in user_msg else ("历史类" if "历史" in user_msg else "综合")
            rank_info = query_yi_fen_yi_duan(province, score, subject, DATA_YEAR)
            if rank_info and rank_info.get("rank"):
                conf_num = rank_info.get("confidence_score", "")
                conf_str = f" 置信度分数:{conf_num}" if conf_num else ""
                hints.append(
                    f"【分数→位次】{province} {score}分 {subject} → 位次约 {rank_info['rank']:,}\n"
                    f"来源：{rank_info['source']}\n"
                    f"置信度：{rank_info['confidence']}{conf_str}"
                )

            for strategy in ["冲", "稳", "保"]:
                matches = query_match_schools_v2(score, province, subject, strategy, year=DATA_YEAR)
                if matches:
                    match_lines = []
                    for m in matches[:5]:
                        badge = ""
                        if m.get("is_985"): badge = "985/"
                        elif m.get("is_211"): badge = "211/"
                        match_lines.append(
                            f"  {m.get('school_name','')[:15]:15}({badge}{m.get('school_level','')}) "
                            f"{m.get('batch','')[:8]:8} "
                            f"最低分{m.get('min_score','')} 位次{m.get('min_rank','')}"
                        )
                    hints.append(
                        f"【{strategy}档位次法推荐】{province} {score}分 {subject}：\n" +
                        "\n".join(match_lines)
                    )
        except Exception as e:
            logging.warning("位次法推荐查询失败: %s", e)
        return hints

    # ── 子方法：百度搜索兜底 ──
    def _fallback_web_search(self, user_msg: str) -> list:
        """数据库无数据时，降级到百度搜索。"""
        search_query = user_msg[:100]
        try:
            baidu_results = web_search(search_query)
        except Exception:
            baidu_results = []
        if baidu_results:
            hint = "【百度搜索结果（仅供参考，请核实官方数据）】\n" + "\n".join(
                f"· {r}" for r in baidu_results[:3]
            )
            return [hint]
        return []

    # ── 子方法：调用 LLM ──
    def _call_llm(self, messages: list) -> str:
        """调用 LLM API 并返回回复文本。"""
        import openai
        start_ts = time.time()
        try:
            kwargs = dict(
                model=CONFIG["model"],
                messages=messages,
                temperature=CONFIG["temperature"],
            )
            if CONFIG["max_tokens"] is not None:
                kwargs["max_tokens"] = CONFIG["max_tokens"]
            resp = self.client.chat.completions.create(**kwargs)
            reply = resp.choices[0].message.content
            elapsed = time.time() - start_ts
            log.info(f"llm_ok model={CONFIG['model']} elapsed={elapsed:.2f}s")
        except openai.RateLimitError as e:
            elapsed = time.time() - start_ts
            log.warning(f"llm_rate_limit model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            reply = "AI 服务繁忙，请稍后重试。"
        except openai.AuthenticationError as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_auth_error model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            reply = "API 配置有误，请联系管理员。"
        except openai.APITimeoutError as e:
            elapsed = time.time() - start_ts
            log.warning(f"llm_timeout model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            reply = "AI 响应超时，请重试。"
        except openai.APIError as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_api_error model={CONFIG['model']} elapsed={elapsed:.2f}s err={type(e).__name__}: {e}")
            reply = "AI 服务出现异常，请稍后重试。"
        except Exception as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_fail model={CONFIG['model']} elapsed={elapsed:.2f}s err={type(e).__name__}: {e}")
            reply = "抱歉，AI 服务暂时不可用，请稍后重试。"
        return reply

    def chat(self, user_msg: str) -> str:
        """处理一轮对话。返回 assistant 的回复。"""
        # #4: Prompt Injection 防御
        if detect_prompt_injection(user_msg):
            return ("不好意思，你的输入包含一些我不太能处理的内容。"
                    "请直接告诉我你的高考情况，我帮你分析志愿。")

        # #13: 输入校验
        user_msg = validate_user_input(user_msg)

        # 埋点：会话追踪
        if HAS_TRACKER:
            if not hasattr(self, '_session_id'):
                import uuid
                self._session_id = uuid.uuid4().hex[:12]
                _tracker.log_event(self._session_id, "session_start", {})

        # 情绪检测（质量控制节点1）
        emotion_result = None
        if HAS_EMOTION_DETECTOR:
            emotion_result = detect_emotion(user_msg)

        # 埋点：情绪检测
        if HAS_TRACKER and emotion_result:
            _tracker.log_event(self._session_id, "emotion_detected", {
                "level": emotion_result["level"],
                "score": emotion_result["score"],
            })

        # 检查意图
        if is_consultation_intent(user_msg):
            # 提取槽位（使用实例自己的 slots）
            updates = extract_slots_from_message(user_msg, self.slots)
        else:
            updates = []

        # 埋点：槽位填充
        if HAS_TRACKER and updates:
            for u in updates:
                parts = u.split("→")
                if len(parts) == 2:
                    _tracker.log_event(self._session_id, "slot_filled",
                                       {"slot_type": parts[0], "slot_value": parts[1][:20]})

        # 构建消息
        system_msg = self._build_system_message()
        # 注入情绪策略（质量控制）
        if emotion_result and emotion_result.get("hint"):
            system_msg += f"\n\n【情绪检测】{emotion_result['hint']}"
            if emotion_result["strategy"] == "crisis":
                hotlines = "\n".join(CRISIS_HOTLINES)
                system_msg += f"\n\n【心理援助热线（仅在用户有自伤信号时提供）】\n{hotlines}"
        messages = [{"role": "system", "content": system_msg}]
        # 添加历史（最近10轮=20条消息）
        for h in self.conversation[-20:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        # 如果有槽位更新，追加提示
        if updates:
            # 当检测到 4+ 个槽位同时被填充时，指示 AI 直接给出推荐
            filled_count = len(filled_slots(self.slots))
            if filled_count >= 4:
                hint = (
                    f"(系统自动识别到: {', '.join(updates)}。"
                    f"用户已提供 {filled_count} 项关键信息，信息充分。"
                    f"请直接查询数据库给出冲稳保推荐，无需再追问。"
                    f"如选科信息已明确，请直接基于选科匹配推荐。)"
                )
            else:
                hint = f"(系统自动识别到: {', '.join(updates)}。请在回复中确认并追问缺失信息。)"
            messages.append({"role": "system", "content": hint})

        # 选科匹配检查
        self._inject_subject_compatibility(messages, user_msg)

        # 语录库注入
        self._inject_quotes(messages, user_msg)

        # ── P2-2: 决策启发式提示注入 ──
        if HAS_DECISION_FRAMEWORK:
            try:
                heuristics = df_recommend_heuristics(self.slots)
                h_descs = "\n".join([f"· {h['name']}：{h['desc']}" for h in heuristics])
                messages.append({
                    "role": "system",
                    "content": f"【决策启发式提示】本回答请优先参考以下启发式：\n{h_descs}"
                })
            except Exception:
                pass  # 静默降级

        # ── P2-2: 模型选择矩阵提示注入 ──
        if HAS_MODEL_SELECTOR:
            try:
                model_result = select_models(self.slots, user_input=user_msg)
                hint = format_model_hint(model_result)
                model_hint = f"【思维框架提示】{hint}"
                if model_result.get("downgrade_triggers"):
                    model_hint += "\n⚠️ 降级触发：" + "；".join(
                        [t["action"] for t in model_result["downgrade_triggers"]]
                    )
                messages.append({"role": "system", "content": model_hint})
            except Exception:
                pass  # 静默降级

        # 数据查询（数据库优先 + 百度兜底）
        data_hints = self._query_data_hints(user_msg)
        if data_hints:
            messages.append({"role": "system", "content": "\n\n".join(data_hints)})

        # 调用 LLM
        reply = self._call_llm(messages)

        # 清理格式：CLI 模式去全部 Markdown，Web 模式保留加粗/列表
        reply = cleanup_format(reply, cli_mode=self.cli_mode)

        # ── P2-2: 决策反模式检测（在自评前运行）──
        if HAS_ANTI_PATTERN_CHECKER:
            try:
                family_known = bool(self.slots.get("family", {}).get("filled"))
                ap_matches = check_anti_patterns(reply, family_known=family_known)
                if ap_matches:
                    from quality.anti_pattern_checker import format_report
                    log.warning(f"anti_pattern_hit count={len(ap_matches)} report={format_report(ap_matches)}")
                    # 如果有 error 级别的反模式，记录但不自动重写（避免影响用户体验）
                    error_count = sum(1 for m in ap_matches if m.severity == "error")
                    if error_count > 0:
                        log.warning(f"anti_pattern_error count={error_count} preview={reply[:80]}")
            except Exception:
                pass  # 静默降级

        # P1-7: 对话质量自评
        eval_score, eval_highlights = self._self_evaluate(reply)
        if eval_score < 40:
            log.warning(f"self_eval_low score={eval_score} reply_len={len(reply)} preview={reply[:60]}")
        # 高分金句入库（>= 60 分才入库）
        if eval_highlights and eval_score >= 60:
            sid = getattr(self, '_session_id', 'cli')
            self._record_highlight(sid, eval_highlights[0], eval_score)

        # 金句候选收集（短回复 + 感叹号/反问号）
        if HAS_TRACKER and reply and len(reply) <= 80 and ("！" in reply or "？" in reply):
            _tracker.log_event(self._session_id, "highlight_candidate", {
                "text": reply[:80],
                "emotion": emotion_result["level"] if emotion_result else "🟢",
            })

        # 对话轮次计数
        self._turn_count = getattr(self, '_turn_count', 0) + 1

        # 对话结束引导（≥3轮且包含推荐关键词）
        if self._turn_count >= 3 and ("冲" in reply or "稳" in reply or "保" in reply):
            if not getattr(self, '_guidance_shown', False):
                reply += "\n\n---\n💡 想要更精准的分析？关注公众号获取：\n1. 个性化 PDF 志愿报告\n2. 500+ 家长真实案例库\n3. 高考季政策实时推送"
                self._guidance_shown = True

        # 保存对话历史
        self.conversation.append({"role": "user", "content": user_msg})
        self.conversation.append({"role": "assistant", "content": reply})

        # 上下文压缩：对话超过阈值时，压缩早期历史为摘要
        self._compress_history()

        # 截断对话历史，防止内存无限增长（保留最近 50 轮 = 100 条消息）
        MAX_HISTORY = 100
        if len(self.conversation) > MAX_HISTORY:
            self.conversation = self.conversation[-MAX_HISTORY:]

        return reply

    # ── 子方法：多轮对话上下文压缩 ──
    _COMPRESS_THRESHOLD = 20   # 对话超过 20 条时触发
    _COMPRESS_KEEP_COUNT = 10  # 保留后 10 条，压缩前 N 条

    def _compress_history(self) -> None:
        """当对话历史超过阈值时，将早期对话压缩为一条摘要，减少 token 消耗。

        纯规则提取，不调用 LLM：
        - 从 user 消息中提取：省份、分数/位次、选科、兴趣、诉求
        - 从 assistant 消息中提取：推荐的学校列表、关键建议
        """
        if len(self.conversation) < self._COMPRESS_THRESHOLD:
            return

        # 取出待压缩的早期消息（保留最近 _COMPRESS_KEEP_COUNT 条不动）
        keep = self.conversation[-self._COMPRESS_KEEP_COUNT:]
        to_compress = self.conversation[:-self._COMPRESS_KEEP_COUNT]

        # ── 从早期消息中提取关键信息 ──
        provinces = set()
        scores = set()
        ranks = set()
        subjects = set()
        interests = set()
        goals = set()
        recommended_schools = set()
        key_advice = []

        for msg in to_compress:
            content = msg.get("content", "")
            if not content:
                continue

            if msg["role"] == "user":
                # 提取省份
                for p in PROVINCES:
                    if p in content:
                        provinces.add(p)
                # 提取分数
                for m in re.finditer(r'(\d{3})\s*分', content):
                    scores.add(m.group(1) + "分")
                # 提取位次
                for m in re.finditer(r'(?:位次|省排|排名)\s*(\d{4,7})', content):
                    ranks.add("位次" + m.group(1))
                for m in re.finditer(r'(\d+(?:\.\d+)?)\s*万\s*(?:位次|名|名次)', content):
                    ranks.add("位次" + str(int(float(m.group(1)) * 10000)))
                # 提取选科
                for subj in ["物理", "历史", "物化生", "物化地", "物化政", "理科", "文科"]:
                    if subj in content:
                        subjects.add(subj)
                        break
                # 提取兴趣
                for kw in ["计算机", "软件", "人工智能", "AI", "电气", "电子信息",
                            "通信", "临床医学", "口腔", "金融", "法学", "会计",
                            "土木", "机械", "新闻", "汉语言", "数学", "化学",
                            "生物", "材料", "环境", "自动化", "集成电路", "大数据"]:
                    if kw in content:
                        interests.add(kw)
                # 提取诉求
                for g in ["就业", "考公", "考研", "稳定", "高薪", "赚钱", "深造", "出国"]:
                    if g in content:
                        goals.add(g)
                        break

            elif msg["role"] == "assistant":
                # 提取推荐的学校名（匹配 xx大学/xx学院）
                for m in re.finditer(r'([一-鿿]{2,8}(?:大学|学院))', content):
                    recommended_schools.add(m.group(1))

        # ── 组装摘要 ──
        parts = ["【对话摘要】（早期对话已压缩，以下为关键信息提取）"]
        if provinces:
            parts.append("省份:" + "、".join(provinces))
        if scores:
            parts.append("分数:" + "、".join(scores))
        if ranks:
            parts.append("位次:" + "、".join(ranks))
        if subjects:
            parts.append("选科:" + "、".join(subjects))
        if interests:
            parts.append("兴趣:" + "、".join(interests))
        if goals:
            parts.append("诉求:" + "、".join(goals))
        if recommended_schools:
            parts.append("已推荐:" + "、".join(list(recommended_schools)[:10]))
        if key_advice:
            parts.append("关键建议:" + "；".join(key_advice[:3]))

        summary_msg = {"role": "system", "content": " | ".join(parts)}

        # 替换：摘要 + 最近的对话
        self.conversation = [summary_msg] + keep

    def chat_stream(self, user_msg: str):
        """流式处理对话。yield 每个 chunk 文本，最后 yield 特殊标记 '|||FINAL|||' + 完整回复。

        用法::

            for chunk in advisor.chat_stream(user_input):
                if chunk.startswith("|||FINAL|||"):
                    final_reply = chunk[len("|||FINAL|||"):]
                else:
                    print(chunk, end="", flush=True)
        """
        # ── 前置逻辑（与 chat() 保持一致）──

        # #4: Prompt Injection 防御
        if detect_prompt_injection(user_msg):
            full_reply = ("不好意思，你的输入包含一些我不太能处理的内容。"
                          "请直接告诉我你的高考情况，我帮你分析志愿。")
            yield full_reply
            yield "|||FINAL|||" + full_reply
            return

        # #13: 输入校验
        user_msg = validate_user_input(user_msg)

        # 埋点：会话追踪
        if HAS_TRACKER:
            if not hasattr(self, '_session_id'):
                import uuid
                self._session_id = uuid.uuid4().hex[:12]
                _tracker.log_event(self._session_id, "session_start", {})

        # 情绪检测（质量控制节点1）
        emotion_result = None
        if HAS_EMOTION_DETECTOR:
            emotion_result = detect_emotion(user_msg)

        # 埋点：情绪检测
        if HAS_TRACKER and emotion_result:
            _tracker.log_event(self._session_id, "emotion_detected", {
                "level": emotion_result["level"],
                "score": emotion_result["score"],
            })

        # 检查意图
        if is_consultation_intent(user_msg):
            updates = extract_slots_from_message(user_msg, self.slots)
        else:
            updates = []

        # 埋点：槽位填充
        if HAS_TRACKER and updates:
            for u in updates:
                parts = u.split("→")
                if len(parts) == 2:
                    _tracker.log_event(self._session_id, "slot_filled",
                                       {"slot_type": parts[0], "slot_value": parts[1][:20]})

        # 构建消息
        system_msg = self._build_system_message()
        if emotion_result and emotion_result.get("hint"):
            system_msg += f"\n\n【情绪检测】{emotion_result['hint']}"
            if emotion_result["strategy"] == "crisis":
                hotlines = "\n".join(CRISIS_HOTLINES)
                system_msg += f"\n\n【心理援助热线（仅在用户有自伤信号时提供）】\n{hotlines}"
        messages = [{"role": "system", "content": system_msg}]
        for h in self.conversation[-20:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        if updates:
            hint = f"(系统自动识别到: {', '.join(updates)}。请在回复中确认并追问缺失信息。)"
            messages.append({"role": "system", "content": hint})

        # 选科匹配检查
        self._inject_subject_compatibility(messages, user_msg)

        # 语录库注入
        self._inject_quotes(messages, user_msg)

        # 数据查询（数据库优先 + 百度兜底）
        data_hints = self._query_data_hints(user_msg)
        if data_hints:
            messages.append({"role": "system", "content": "\n\n".join(data_hints)})

        # ── 流式调用 LLM ──
        import openai
        start_ts = time.time()
        full_reply = ""
        try:
            kwargs = dict(
                model=CONFIG["model"],
                messages=messages,
                temperature=CONFIG["temperature"],
                stream=True,
            )
            if CONFIG["max_tokens"] is not None:
                kwargs["max_tokens"] = CONFIG["max_tokens"]
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    text_piece = delta.content
                    full_reply += text_piece
                    yield text_piece
            elapsed = time.time() - start_ts
            log.info(f"llm_stream_ok model={CONFIG['model']} elapsed={elapsed:.2f}s len={len(full_reply)}")
        except openai.RateLimitError as e:
            elapsed = time.time() - start_ts
            log.warning(f"llm_stream_rate_limit model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            full_reply = "AI 服务繁忙，请稍后重试。"
            yield full_reply
        except openai.AuthenticationError as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_stream_auth_error model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            full_reply = "API 配置有误，请联系管理员。"
            yield full_reply
        except openai.APITimeoutError as e:
            elapsed = time.time() - start_ts
            log.warning(f"llm_stream_timeout model={CONFIG['model']} elapsed={elapsed:.2f}s err={e}")
            full_reply = "AI 响应超时，请重试。"
            yield full_reply
        except openai.APIError as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_stream_api_error model={CONFIG['model']} elapsed={elapsed:.2f}s err={type(e).__name__}: {e}")
            full_reply = "AI 服务出现异常，请稍后重试。"
            yield full_reply
        except Exception as e:
            elapsed = time.time() - start_ts
            log.error(f"llm_stream_fail model={CONFIG['model']} elapsed={elapsed:.2f}s err={type(e).__name__}: {e}")
            full_reply = "抱歉，AI 服务暂时不可用，请稍后重试。"
            yield full_reply

        # ── 后处理（与 chat() 一致）──

        # 清理格式：Web 模式保留加粗/列表
        full_reply = cleanup_format(full_reply, cli_mode=self.cli_mode)

        # P1-7: 对话质量自评
        eval_score, eval_highlights = self._self_evaluate(full_reply)
        if eval_score < 40:
            log.warning(f"self_eval_low score={eval_score} reply_len={len(full_reply)} preview={full_reply[:60]}")
        # 高分金句入库（>= 60 分才入库）
        if eval_highlights and eval_score >= 60:
            sid = getattr(self, '_session_id', 'cli')
            self._record_highlight(sid, eval_highlights[0], eval_score)

        # 金句候选收集
        if HAS_TRACKER and full_reply and len(full_reply) <= 80 and ("！" in full_reply or "？" in full_reply):
            _tracker.log_event(self._session_id, "highlight_candidate", {
                "text": full_reply[:80],
                "emotion": emotion_result["level"] if emotion_result else "\U0001f7e2",
            })

        # 对话轮次计数
        self._turn_count = getattr(self, '_turn_count', 0) + 1

        # 对话结束引导（>=3轮且包含推荐关键词）
        if self._turn_count >= 3 and ("冲" in full_reply or "稳" in full_reply or "保" in full_reply):
            if not getattr(self, '_guidance_shown', False):
                full_reply += "\n\n---\n\U0001f4a1 想要更精准的分析？关注公众号获取：\n1. 个性化 PDF 志愿报告\n2. 500+ 家长真实案例库\n3. 高考季政策实时推送"
                self._guidance_shown = True

        # 保存对话历史
        self.conversation.append({"role": "user", "content": user_msg})
        self.conversation.append({"role": "assistant", "content": full_reply})

        # 上下文压缩：对话超过阈值时，压缩早期历史为摘要
        self._compress_history()

        # 截断对话历史
        MAX_HISTORY = 100
        if len(self.conversation) > MAX_HISTORY:
            self.conversation = self.conversation[-MAX_HISTORY:]

        # yield 最终标记（供调用方做卡片解析、持久化等）
        yield "|||FINAL|||" + full_reply

    # ── P1-7: 对话质量自评 ────────────────────────────────
    _FORBIDDEN_WORDS = ["或许", "可能", "综合评估", "建议您", "仅供参考"]

    def _self_evaluate(self, reply: str) -> tuple[int, list[str]]:
        """对 AI 回复进行自评打分（0-100），并提取金句候选。

        8 项自检清单（满分 100）：
          a. 第一句话给了明确判断（不含问候）       — 15 分
          b. 有金句（<=30字的收尾句）               — 15 分
          c. 避免禁词（或许/可能/综合评估/建议您/仅供参考） — 15 分
          d. 口语化比例 >= 70%                      — 15 分
          e. 引用数据并标注来源                     — 10 分
          f. 未编造数据（"根据""数据显示"等需有真实出处） — 10 分
          g. 回复长度合理（50-800字）               — 10 分
          h. 不含 Markdown 格式残留                 — 10 分

        Returns:
            (score, highlights): 分数和金句列表（最多 1 条）
        """
        if not reply or not reply.strip():
            return 0, []

        score = 0
        highlights: list[str] = []
        lines = [l.strip() for l in reply.strip().splitlines() if l.strip()]

        # a. 第一句话给明确判断（不含问候寒暄，15 分）
        first_line = lines[0] if lines else ""
        _greeting_words = ["你好", "您好", "嗨", "很高兴", "欢迎", "感谢"]
        if first_line and not any(g in first_line for g in _greeting_words):
            # 至少包含一个判断性词汇
            _judgment_words = [
                "别", "千万别", "必须", "建议", "应该", "选", "不选",
                "推荐", "冲", "稳", "保", "方向", "明确", "首选",
                "最优", "是最好的", "别碰", "别想", "不行", "可以",
            ]
            if any(j in first_line for j in _judgment_words):
                score += 15
            else:
                score += 7  # 有开头但缺乏明确判断

        # b. 有金句（<=30字的收尾句，15 分）
        last_line = lines[-1] if lines else ""
        # 收尾句通常是一句总结性的话
        if 4 <= len(last_line) <= 30:
            score += 15
            highlights.append(last_line)
        elif 4 <= len(last_line) <= 50:
            score += 8  # 稍长，部分得分
            # 从最后几行中提取最短的一句作为金句
            for line in reversed(lines[-3:]):
                if 4 <= len(line) <= 30:
                    highlights.append(line)
                    break

        # c. 避免禁词（15 分）
        found_forbidden = [w for w in self._FORBIDDEN_WORDS if w in reply]
        if not found_forbidden:
            score += 15
        else:
            # 每出现一个禁词扣 5 分，最低 0
            score += max(0, 15 - len(found_forbidden) * 5)

        # d. 口语化比例 >= 70%（15 分）
        sentences = re.split(r'[。！？\n]', reply)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 2]
        if sentences:
            oral_count = 0
            for s in sentences:
                # 短句（<=40字）算口语化；含语气词（吧、呢、啊、嘛、呀、噢）也算
                if len(s) <= 40 or any(p in s for p in "吧呢啊嘛呀噢嘿"):
                    oral_count += 1
            oral_ratio = oral_count / len(sentences)
            if oral_ratio >= 0.7:
                score += 15
            elif oral_ratio >= 0.5:
                score += 10
            elif oral_ratio >= 0.3:
                score += 5

        # e. 引用数据并标注来源（10 分）
        _data_source_patterns = [
            r'根据.*?(?:数据|评估|报告|统计|显示)',
            r'教育部',
            r'数据库显示',
            r'来源[：:]',
            r'数据显示',
            r'录取线|录取分',
            r'就业率',
            r'\d{4}年',
        ]
        has_data_citation = any(re.search(p, reply) for p in _data_source_patterns)
        if has_data_citation:
            score += 10

        # f. 未编造数据（10 分）
        # 检查"根据X数据"、"数据显示"等是否有具体来源
        _vague_data = re.findall(r'(?:根据|据)\s*.{0,10}(?:数据|统计|报告)', reply)
        _vague_display = re.findall(r'数据显示', reply)
        vague_count = len(_vague_data) + len(_vague_display)
        # 如果有具体年份/机构名，不算编造
        _specific_sources = re.findall(
            r'(?:教育部|麦可思|百度高考|省考试院|阳光高考|\d{4}年)', reply
        )
        if vague_count == 0 or len(_specific_sources) >= vague_count:
            score += 10
        elif len(_specific_sources) > 0:
            score += 5

        # g. 回复长度合理（50-800字，10 分）
        reply_len = len(reply)
        if 50 <= reply_len <= 800:
            score += 10
        elif 30 <= reply_len <= 1200:
            score += 5
        # 过短（<30）或过长（>1200）不得分

        # h. 不含 Markdown 格式残留（10 分）
        md_patterns = [r'^#{1,6}\s', r'\*\*.*?\*\*', r'^\s*[-*]\s+', r'^\s*\d+[\.、]\s+']
        md_count = sum(1 for p in md_patterns if re.search(p, reply, re.MULTILINE))
        if md_count == 0:
            score += 10
        elif md_count <= 1:
            score += 5

        return min(score, 100), highlights[:1]  # 最多 1 条金句

    def _record_highlight(self, session_id: str, content: str, score: int) -> None:
        """将高分金句持久化到 highlights 表。"""
        try:
            from db.database import get_session
            from db.models import Highlight
            db = get_session()
            try:
                db.add(Highlight(session_id=session_id, content=content, score=score))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logging.warning("金句入库失败: %s", e)

    def reset(self) -> None:
        """重置对话和槽位。"""
        self.conversation = []
        for k in self.slots:
            self.slots[k]["filled"] = False
            self.slots[k]["value"] = ""

# ── CLI 界面 ─────────────────────────────────────────
def test_connection():
    """测试 API 连接是否正常。"""
    try:
        client = OpenAI(base_url=CONFIG["base_url"], api_key=CONFIG["api_key"])
        resp = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return True, resp.choices[0].message.content
    except Exception as e:
        return False, str(e)

def main():
    import textwrap

    print("=" * 60)
    print("  高考志愿顾问 Agent")
    print(f"  模型: {CONFIG['model']}")
    print(f"  搜索: {'开' if CONFIG['enable_search'] else '关'}")
    print("=" * 60)

    if not CONFIG["api_key"]:
        print("\n❌ 未检测到 API Key！")
        print("   请复制 .env.example 为 .env 并填入你的 API Key。")
        print("   或者设置环境变量 LLM_API_KEY=你的key")
        print()
        print("   快速开始（任选一种）：")
        print("   · DeepSeek:  set LLM_PROVIDER=deepseek && set LLM_API_KEY=sk-xxx")
        print("   · 通义千问:  set LLM_PROVIDER=qwen && set LLM_API_KEY=sk-xxx")
        print("   · 智谱GLM:   set LLM_PROVIDER=glm && set LLM_API_KEY=xxx")
        input("\n   按回车退出...")
        return

    # 测试连接
    print("  正在测试 API 连接...", end=" ", flush=True)
    ok, msg = test_connection()
    if ok:
        print("[OK] 连接成功")
    else:
        print(f"[X] 连接失败: {msg[:200]}")
        print()
        # 智能诊断
        if "401" in msg or "Authentication" in msg:
            print("   → Key 无效或格式错误。检查：")
            print("   1. Key 是不是 sk- 完整开头？前后有没有空格？")
            print("   2. 去 API 平台确认 Key 状态是'有效'")
            print("   3. 试试只留两行：LLM_PROVIDER=deepseek + LLM_API_KEY=你的key")
        elif "402" in msg or "Insufficient" in msg or "Balance" in msg:
            print("   → 账户余额不足！去 API 平台充值，或换通义千问（有免费额度）")
        elif "403" in msg or "Forbidden" in msg:
            print("   → Key 没有权限。检查 Key 是否开通了 chat/completions 接口")
        elif "404" in msg or "Not Found" in msg:
            print("   → 接口地址不对。试试 BASE_URL 末尾加 /v1")
        elif "timeout" in msg.lower() or "connect" in msg.lower():
            print("   → 网络连不上 API 服务器。检查网络/代理")
        else:
            print("   检查 .env 中 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
        input("\n   按回车退出...")
        return

    print("=" * 60)
    print("  命令: /paste 粘贴 | /slots 信息 | /reset 重置 | /quit 退出")
    print("  直接描述你的情况，我会帮你分析。")
    print("=" * 60)
    print()

    advisor = GaokaoAdvisor(cli_mode=True)

    while True:
        try:
            user_input = input("\n[You] 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见！")
            break
        elif user_input == "/reset":
            advisor.reset()
            print("[OK] 已重置对话和信息采集")
            continue
        elif user_input == "/slots":
            print(slots_summary(advisor.slots))
            continue
        elif user_input == "/stats":
            if HAS_TRACKER:
                stats = _tracker.get_stats(days=7)
                print(f"\n📊 运营数据（最近 {stats.get('days', 7)} 天）")
                print("━" * 30)
                print(f"会话数: {stats['session_count']}")
                if stats.get('emotion_distribution'):
                    print(f"\n😊 情绪分布:")
                    for level, count in stats['emotion_distribution'].items():
                        print(f"  {level}: {count}")
                if stats.get('top_majors'):
                    print(f"\n📚 热门专业 TOP 5:")
                    for name, count in stats['top_majors'][:5]:
                        print(f"  {name}({count})")
                if stats.get('top_schools'):
                    print(f"\n🏫 热门学校 TOP 5:")
                    for name, count in stats['top_schools'][:5]:
                        print(f"  {name}({count})")
            else:
                print("埋点模块不可用")
            continue
        elif user_input == "/paste":
            cb = read_clipboard()
            if cb and cb.strip():
                user_input = " ".join(cb.strip().split("\n"))
                print(f"📋 剪贴板已读取 ({len(user_input)}字)")
                print(f"📋 内容: {user_input[:100]}...")
            else:
                print("📋 剪贴板为空或无法读取")
                continue

        print("\n🤖 顾问: ", end="", flush=True)
        reply = advisor.chat(user_input)
        print(reply)

if __name__ == "__main__":
    main()
