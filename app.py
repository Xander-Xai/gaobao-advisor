#!/usr/bin/env python3
"""
高报Agent · AI 高考志愿顾问 — Streamlit Web 前端
复用 agent.py 的核心逻辑，提供移动端友好的聊天界面。
Usage:
  streamlit run app.py
"""

import os
import sys
import time
import uuid
import hmac
import re as _re
import logging
import html
import json as _json
import streamlit as st

# ── 页面配置（必须是第一个 st 命令）────────────────────
st.set_page_config(
    page_title="高报Agent · AI 高考志愿顾问",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Streamlit Cloud Secrets 支持 ─────────────────────
# 如果在 Streamlit Cloud 上运行，从 st.secrets 加载环境变量
# 本地运行时则从 .env 文件加载（由 agent.py 的 dotenv 处理）
try:
    if hasattr(st, "secrets") and st.secrets:
        for key in ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_PROVIDER",
                    "ENABLE_SEARCH"]:
            val = st.secrets.get(key)
            if val:
                os.environ[key] = str(val)
except Exception:
    # 没有 secrets.toml 文件时忽略，使用 .env 配置
    pass

# 确保当前目录在 path 中，以便导入 agent 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import (
    GaokaoAdvisor,
    slots_summary,
    PROVINCES,
)
from ratelimit import RateLimiter

# 进程级限流器单例（解决多 tab 绕过限流的竞态问题）
_GLOBAL_RATE_LIMITER = RateLimiter(
    hourly_limit=20,
    daily_limit=40,
    max_input_len=500,
)

# ── 常量 ─────────────────────────────────────────────

# #19: 应用级密码认证（通过环境变量 APP_PASSWORD 启用）
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

WELCOME_MSG = (
    "你好！我是 **高报Agent AI 高考志愿顾问**，说话直、不绕弯，专门帮你解决志愿填报难题。\n\n"
    "**先告诉我你是哪个省的？考了多少分？** 我马上帮你分析能上什么学校。\n\n"
    "📌 **简单 3 步**：\n"
    "1️⃣ 说清楚省份和分数（位次也行）\n"
    "2️⃣ 告诉我你想学什么 / 想去哪 / 最在意什么\n"
    "3️⃣ 拿到专属的冲稳保推荐\n\n"
    "👇 直接打字或点下方快速提问："
)

# 场景化快速提问（按用户类型分组，不限定具体省份）
QUICK_QUESTIONS = [
    "📍 我是[XX省]考生，想让你帮我分析",
    "🎯 我是高分考生，想冲 985/211",
    "💼 我想找好就业的专业，怎么选？",
    "📝 我想考公/考研，应该报什么？",
    "😰 孩子考得不理想，帮我看看有什么选择",
    "❓ 我对志愿填报一无所知，从哪开始？",
]

# 免责声明三件套之一：欢迎消息末尾的合规提示
DISCLAIMER_BRIEF = (
    "⚠️ **免责声明**：本顾问基于公开数据与 AI 推理生成建议，"
    "**仅供参考，不构成升学建议**。最终志愿以高校官方招生章程、"
    "省考试院公布数据为准，请勿输入身份证号、真实姓名等敏感信息。"
)

TIPS = [
    "先说省份和分数，我能更快帮你分析",
    "可以说出喜欢/讨厌的专业方向",
    "告诉我你在意什么：就业、考研、城市、离家远近",
    "随时输入 `/reset` 重新开始对话",
    "⚠️ 不要输入身份证号、真实姓名、银行卡等敏感信息",
]


# ── 数据脱敏 & 隐私守卫（合规） ─────────────────────
# 防止用户不小心把敏感个人信息（身份证 / 真实姓名 / 手机 / 银行卡）输入到对话里
# 检测到后给出友好提示并建议重新输入

# 身份证号（18位 / 15位，含地址码、生日码、顺序码、校验码）
# 注意：中文 + 数字场景下 \b 不可靠，改用 (?<!\d)...(?!\d) 数字边界
_RE_ID_CARD = _re.compile(
    r'(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)'
)
# 中国大陆手机号（11位，1开头，3-9 第二位）
_RE_MOBILE = _re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')
# 银行卡号（16-19位连续数字，宽松匹配，但需排除已命中的身份证号）
_RE_BANK = _re.compile(r'(?<!\d)\d{16,19}(?!\d)')
# 真实姓名启发式关键词 + 高考常用词黑名单
# 策略：捕获 2-3 个汉字（最多3字），后跟非汉字字符（如"580分"的"5"）
# 这样"我是山东考生"里"我是"后紧跟"山东"（2字后跟"考"）→ 捕获"山东"
#        而"我是李明，"里"我是"后跟"李明"（2字后跟"，"）→ 捕获"李明"
_REAL_NAME_BLOCKLIST = frozenset({
    "山东", "考生", "学生", "同学", "老师", "家长",
    "父母", "父亲", "母亲", "姐妹", "兄弟", "高三", "今年",
    "湖北", "河南", "河北", "湖南", "广东", "广西", "四川",
    "浙江", "江苏", "安徽", "福建", "山西", "陕西", "江西",
    "甘肃", "贵州", "云南", "海南", "吉林", "辽宁", "北京",
    "上海", "天津", "重庆", "西藏", "宁夏", "新疆", "内蒙",
    "黑龙江", "内蒙古", "青海",
})
_RE_REAL_NAME = _re.compile(
    r'(?:我叫|我是|我儿子叫|我女儿叫|我同学叫|我朋友叫|考生姓名|姓名)'
    r'\s*([一-龥]{2,3}?)(?=[^一-龥]|$)',
    _re.UNICODE
)

# QQ号（5-11位纯数字，一般以1开头；需排除已匹配的手机号和身份证号）
# 先用宽泛模式匹配，再在检测函数中做排除
_RE_QQ = _re.compile(r'(?<!\d)[1-9]\d{4,10}(?!\d)')
# 微信号（6-20位，字母开头，可含字母、数字、减号、下划线）
_RE_WECHAT = _re.compile(r'(?<![a-zA-Z0-9_-])[a-zA-Z][a-zA-Z0-9_-]{5,19}(?![a-zA-Z0-9_-])')
# 微信号常见误判单词黑名单（小写比较）
_WECHAT_BLOCKLIST = frozenset({
    "student", "teacher", "python", "select", "system", "public",
    "import", "export", "return", "string", "number", "default",
    "update", "delete", "create", "insert", "global", "module",
    "config", "output", "input", "error", "result", "object",
    "thread", "server", "client", "master", "status", "format",
    "button", "submit", "cancel", "search", "common", "normal",
    "active", "public", "static", "double", "simple", "single",
})
# 家庭住址（含路/街/小区/栋/单元/号/弄/巷/村等关键词 + 数字组合）
_RE_ADDRESS = _re.compile(
    r'(?:省|市|区|县|镇|乡|村|路|街|大道|小区|弄|巷|号|栋|单元|室|楼)'
    r'\s*\d+'
)


def detect_sensitive_info(text: str) -> list:
    """
    检测用户输入中的敏感信息。返回命中的敏感类型列表。
    用于前置警告用户，避免不必要的数据采集风险。
    """
    hits = []
    if _RE_ID_CARD.search(text):
        hits.append("身份证号")
    if _RE_MOBILE.search(text):
        hits.append("手机号")
    if _RE_BANK.search(text):
        # 银行卡误判去重：排除已经命中身份证号的那串数字
        # 如果这串 16-19 位数字也同时符合身份证号结构，不算银行卡
        id_match = _RE_ID_CARD.search(text)
        bank_match = _RE_BANK.search(text)
        if bank_match and (not id_match or bank_match.group() != id_match.group()):
            hits.append("银行卡号")
    if _RE_REAL_NAME.search(text):
        # 二次过滤：排除高考场景常用词（前缀匹配，覆盖"湖北人""山东人"等）
        for m in _RE_REAL_NAME.finditer(text):
            name = m.group(1).strip()
            if any(name.startswith(bl) for bl in _REAL_NAME_BLOCKLIST):
                continue
            hits.append("真实姓名")
            break
    # QQ号检测：排除已命中的手机号和身份证号覆盖的数字
    if _RE_QQ.search(text):
        id_match = _RE_ID_CARD.search(text)
        mobile_match = _RE_MOBILE.search(text)
        for m in _RE_QQ.finditer(text):
            val = m.group()
            # 排除手机号（11位，1[3-9]开头）
            if mobile_match and val == mobile_match.group():
                continue
            # 排除身份证号子串
            if id_match and val == id_match.group():
                continue
            # 排除银行卡号子串（16-19位 QQ号不可能这么长，但以防万一）
            if len(val) == 11 and val.startswith('1') and val[1] in '3456789':
                continue
            hits.append("QQ号")
            break
    # 微信号检测：排除常见英文单词
    if _RE_WECHAT.search(text):
        for m in _RE_WECHAT.finditer(text):
            val = m.group()
            if val.lower() not in _WECHAT_BLOCKLIST:
                hits.append("微信号")
                break
    # 家庭住址检测
    if _RE_ADDRESS.search(text):
        hits.append("家庭住址")
    return hits


SENSITIVE_WARNING = (
    "🔒 **检测到敏感信息**\n\n"
    "你刚才的输入中包含 {kinds}。请不要在对话里输入任何真实个人信息。\n\n"
    "**为什么重要**：\n"
    "- 本服务会存储对话记录以便恢复会话，但安全起见请勿输入\n"
    "- 涉及身份证/姓名/手机号/QQ号/微信号/家庭住址属于《个人信息保护法》规制范围\n\n"
    "**建议**：\n"
    "- 改用「某同学」「考生A」等匿名代称\n"
    "- 分数、位次、选科、兴趣方向等都是非敏感信息，可以正常输入\n\n"
    "—— 我已经把你的敏感信息**自动从记忆中清除**，请重新输入你想问的问题。"
)


# ── 学校卡片渲染 ──
# 解析 agent 输出中的结构化数据标记 `<!--SCHOOL_DATA:...-->`
# 渲染为可视化的冲/稳/保卡片
import html as _html


_SCHOOL_CARD_CSS = """
.school-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #3b82f6;
    border-radius: 8px;
    padding: 0.7rem 0.9rem;
    margin: 0.4rem 0;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.school-card-chong { border-left-color: #ef4444; background: #fef2f2; }
.school-card-wen { border-left-color: #3b82f6; background: #eff6ff; }
.school-card-bao { border-left-color: #22c55e; background: #f0fdf4; }
.school-card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 0.2rem;
}
.school-card-tags {
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
    margin: 0.2rem 0 0.4rem 0;
}
.school-card-tag {
    font-size: 0.72rem;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    background: #e0e7ff;
    color: #3730a3;
    font-weight: 500;
}
.school-card-tag-985 { background: #fee2e2; color: #991b1b; }
.school-card-tag-211 { background: #fef3c7; color: #92400e; }
.school-card-tag-dfc { background: #ddd6fe; color: #5b21b6; }
.school-card-meta {
    font-size: 0.82rem;
    color: #4b5563;
    line-height: 1.5;
}
.school-card-meta b { color: #1f2937; }
.school-group-title {
    font-weight: 700;
    font-size: 0.95rem;
    margin: 0.6rem 0 0.3rem 0;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    display: inline-block;
}
.school-group-chong { color: #991b1b; background: #fee2e2; }
.school-group-wen { color: #1e40af; background: #dbeafe; }
.school-group-bao { color: #166534; background: #dcfce7; }

/* 专业百科卡片 (P2-6) */
.major-card {
    background: linear-gradient(135deg, #faf5ff 0%, #eff6ff 100%);
    border: 1px solid #c4b5fd;
    border-left: 4px solid #8b5cf6;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    box-shadow: 0 2px 4px rgba(139, 92, 246, 0.08);
}
.major-card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #5b21b6;
    margin-bottom: 0.3rem;
}
.major-card-body {
    font-size: 0.85rem;
    color: #374151;
    line-height: 1.6;
}
.major-card-body b { color: #1f2937; }
.major-card-tag {
    display: inline-block;
    font-size: 0.72rem;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    background: #ede9fe;
    color: #5b21b6;
    font-weight: 500;
    margin-right: 0.3rem;
}
"""


_SCHOOL_DATA_PATTERN = _re.compile(
    r'<!--SCHOOL_DATA:(.*?)-->', _re.DOTALL
)


def _render_school_card(school: dict) -> str:
    """渲染单个学校卡片。"""
    name = _html.escape(str(school.get("name", "未知院校")))
    city = _html.escape(str(school.get("city", "")))
    province = _html.escape(str(school.get("province", "")))
    level = str(school.get("level", "")).strip()
    score = school.get("min_score")
    rank = school.get("min_rank")
    year = school.get("year", "")
    batch = _html.escape(str(school.get("batch", "")))
    subject = _html.escape(str(school.get("subject_type", "")))
    major = _html.escape(str(school.get("major", "院校线")))
    note = _html.escape(str(school.get("note", "")))
    group = str(school.get("group", "wen")).strip()  # chong/wen/bao

    # 标签
    tags = []
    if "985" in level:
        tags.append('<span class="school-card-tag school-card-tag-985">985</span>')
    if "211" in level:
        tags.append('<span class="school-card-tag school-card-tag-211">211</span>')
    if "双一流" in level or school.get("is_double_first_class"):
        tags.append('<span class="school-card-tag school-card-tag-dfc">双一流</span>')
    if level and level not in ("985", "211", "双一流"):
        tags.append(f'<span class="school-card-tag">{_html.escape(level)}</span>')

    # 元信息
    meta_parts = []
    if city:
        meta_parts.append(f"📍 {city}")
    elif province:
        meta_parts.append(f"📍 {province}")
    if major and major != "院校线":
        meta_parts.append(f"🎓 {major}")
    if batch:
        meta_parts.append(f"📋 {batch}")
    if subject:
        meta_parts.append(f"📚 {subject}")
    if year:
        meta_parts.append(f"📅 {year}年")
    meta = " · ".join(meta_parts)

    # 分数信息
    score_parts = []
    if score is not None and score != "":
        score_parts.append(f"最低分 <b>{score}</b>")
    if rank is not None and rank != "":
        score_parts.append(f"最低位次 <b>{rank}</b>")

    card_class = f"school-card school-card-{group}"
    tag_html = "".join(tags)
    meta_html = f'<div class="school-card-meta">{meta}</div>' if meta else ""
    score_html = (
        f'<div class="school-card-meta">{" | ".join(score_parts)}</div>'
        if score_parts else ""
    )
    note_html = f'<div class="school-card-meta">{note}</div>' if note else ""

    return f"""
<div class="{card_class}">
    <div class="school-card-title">{name}</div>
    <div class="school-card-tags">{tag_html}</div>
    {meta_html}
    {score_html}
    {note_html}
</div>
"""


# ── 专业百科卡片渲染（P2-6）──
_MAJOR_ENCYCLOPEDIA_RE = _re.compile(r'【专业百科】(.+?)(?=\n【|\n---|\Z)', _re.DOTALL)


def _render_major_card(text: str) -> str:
    """将 【专业百科】XX专业 | key:value | ... 格式化为 HTML 卡片。"""
    parts = [p.strip() for p in text.split("|")]
    if not parts:
        return _html.escape(text)

    title = parts[0]
    fields_html = []
    for p in parts[1:]:
        if ":" in p:
            key, _, val = p.partition(":")
            fields_html.append(f"<b>{_html.escape(key.strip())}</b>: {_html.escape(val.strip())}")
        else:
            fields_html.append(_html.escape(p))

    body = " &middot; ".join(fields_html)
    return f"""
<div class="major-card">
    <div class="major-card-title">📘 {_html.escape(title)}</div>
    <div class="major-card-body">{body}</div>
</div>
"""


def _render_school_cards(reply_text: str) -> str:
    """
    解析回复中的学校数据标记，渲染为卡片。
    非 SCHOOL_DATA 部分做 HTML 转义（防止 LLM 输出的恶意 HTML 被执行）。
    支持两种格式：
    1. <!--SCHOOL_DATA:[{...},{...}]-->
    2. <!--SCHOOL_DATA:{...}-->  (单个学校)
    """
    # 先提取所有 SCHOOL_DATA 标记的位置
    parts = []
    last_end = 0
    for match in _SCHOOL_DATA_PATTERN.finditer(reply_text):
        # 非 SCHOOL_DATA 部分：HTML 转义后保留
        before = reply_text[last_end:match.start()]
        if before:
            parts.append(_html.escape(before))

        # SCHOOL_DATA 部分：解析并渲染卡片
        raw = match.group(1).strip()
        try:
            data = _json.loads(raw)
        except Exception:
            parts.append(_html.escape(match.group(0)))
            last_end = match.end()
            continue
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            parts.append(_html.escape(match.group(0)))
            last_end = match.end()
            continue

        # 按 group 分组
        groups = {"chong": [], "wen": [], "bao": []}
        for s in data:
            g = str(s.get("group", "wen")).strip()
            if g not in groups:
                g = "wen"
            groups[g].append(s)

        for g_key, g_label, g_class in [
            ("chong", "🚀 冲一冲", "school-group-chong"),
            ("wen", "🎯 稳一稳", "school-group-wen"),
            ("bao", "🛡️ 保一保", "school-group-bao"),
        ]:
            items = groups[g_key]
            if not items:
                continue
            parts.append(
                f'<div class="school-group-title {g_class}">{g_label}'
                f'（{len(items)} 所）</div>'
            )
            for s in items[:5]:  # 每组最多 5 张卡片
                parts.append(_render_school_card(s))
        last_end = match.end()

    # 尾部剩余文本
    tail = reply_text[last_end:]
    if tail:
        parts.append(_html.escape(tail))

    # P2-6: 在最终 HTML 中，将 【专业百科】... 替换为卡片样式
    result = "".join(parts)
    result = _MAJOR_ENCYCLOPEDIA_RE.sub(
        lambda m: _render_major_card(m.group(1)),
        result,
    )
    return result



# ── 自定义样式：移动端优化 + 暖色教育风格 ─────────────
st.markdown(
    """
    <style>
    /* 全局字体和背景 */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                     "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    }

    /* 顶部标题栏 */
    .main-title {
        text-align: center;
        padding: 0.6rem 0 0.2rem 0;
        margin-bottom: 0.3rem;
    }
    .main-title h1 {
        font-size: 1.4rem;
        color: #1a56db;
        margin: 0;
    }
    .main-title p {
        font-size: 0.85rem;
        color: #6b7280;
        margin: 0;
    }

    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
    }

    /* 欢迎卡片 */
    .welcome-card {
        background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%);
        border: 1px solid #bfdbfe;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }

    /* 提示标签 */
    .tip-item {
        background: #f8fafc;
        border-left: 3px solid #3b82f6;
        padding: 0.4rem 0.8rem;
        margin: 0.3rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
        color: #374151;
    }

    /* 免费次数提醒 */
    .counter-badge {
        text-align: center;
        padding: 0.5rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
    }
    .counter-ok {
        background: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
    }
    .counter-warn {
        background: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .counter-limit {
        background: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }

    /* 升级提示 */
    .upgrade-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 1px solid #f59e0b;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        margin: 0.8rem 0;
    }
    .upgrade-box a {
        display: inline-block;
        background: #f59e0b;
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        margin-top: 0.5rem;
    }

    /* 槽位进度条 */
    .slot-bar {
        display: flex;
        gap: 4px;
        margin: 0.4rem 0;
    }
    .slot-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
    }
    .slot-filled { background: #22c55e; }
    .slot-empty { background: #e5e7eb; }

    /* 移动端适配 */
    @media (max-width: 768px) {
        .main-title h1 { font-size: 1.2rem; }
        .stChatMessage { font-size: 0.9rem; }
    }

    /* 分阶段加载提示 */
    .loading-step {
        background: #eff6ff;
        border-left: 3px solid #3b82f6;
        padding: 0.5rem 0.8rem;
        border-radius: 0 8px 8px 0;
        color: #1e40af;
        font-size: 0.9rem;
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* 隐藏 Streamlit 默认的 hamburger menu 和 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# 注入学校卡片样式
st.markdown(f"<style>{_SCHOOL_CARD_CSS}</style>", unsafe_allow_html=True)


# ── Session State 初始化 ──────────────────────────────
def init_session():
    """初始化 session state 中的顾问实例和计数器。"""
    # 先初始化 per-session 的 slots（每个用户独立）
    if "slots" not in st.session_state:
        st.session_state.slots = {
            "province":     {"label": "省份", "filled": False, "value": ""},
            "score_rank":   {"label": "分数/位次", "filled": False, "value": ""},
            "subject":      {"label": "选科", "filled": False, "value": ""},
            "interest":     {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
            "region":       {"label": "地域偏好", "filled": False, "value": ""},
            "family":       {"label": "家庭资源", "filled": False, "value": ""},
            "goal":         {"label": "核心诉求", "filled": False, "value": ""},
        }
    # API Key 输入状态
    if "user_api_key" not in st.session_state:
        st.session_state.user_api_key = ""
    if "api_key_confirmed" not in st.session_state:
        st.session_state.api_key_confirmed = False
    if "msg_count" not in st.session_state:
        st.session_state.msg_count = 0
    if "messages" not in st.session_state:
        # messages 用于存储 Streamlit 聊天 UI 的显示记录
        st.session_state.messages = []
    if "limit_reached" not in st.session_state:
        st.session_state.limit_reached = False
    # #10: 频率限制状态
    if "last_request_time" not in st.session_state:
        st.session_state.last_request_time = 0.0
    # #19: 密码认证状态
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    # P3: 对话持久化 — session_id（URL 参数 + cookie 双保险）
    if "session_id" not in st.session_state:
        # 优先从 URL 参数恢复
        params = st.query_params
        url_sid = params.get("sid")
        if url_sid and len(url_sid) >= 12:
            st.session_state.session_id = url_sid
        else:
            st.session_state.session_id = uuid.uuid4().hex  # 128 位完整 UUID
            st.query_params["sid"] = st.session_state.session_id
    # P3: 首次加载时，尝试从数据库恢复历史对话
    if "history_restored" not in st.session_state:
        st.session_state.history_restored = False
    if not st.session_state.history_restored and not st.session_state.messages:
        _try_restore_history()
        st.session_state.history_restored = True

# #10: 频率限制常量
MIN_REQUEST_INTERVAL = 2.0  # 秒，两次请求之间最短间隔
MAX_MSG_PER_SESSION = 50    # 单 session 最大消息数


# ── P3: 对话持久化辅助函数 ─────────────────────────────
def _try_restore_history():
    """从数据库恢复历史对话和槽位信息。"""
    try:
        from db.database import get_session
        from db.crud import load_conversation_history, load_conversation_slots
        db = get_session()
        try:
            history = load_conversation_history(db, st.session_state.session_id)
            if history:
                st.session_state.messages = history
                st.session_state.msg_count = len(history)
            # 恢复槽位
            saved_slots = load_conversation_slots(db, st.session_state.session_id)
            if saved_slots:
                for k, v in saved_slots.items():
                    if k in st.session_state.slots and isinstance(v, dict):
                        st.session_state.slots[k] = v
        finally:
            db.close()
    except Exception as e:
        logging.debug("恢复历史对话失败（数据库不可用时正常）: %s", e)


def _save_message_to_db(role: str, content: str):
    """将一条消息保存到数据库（异步友好，失败不影响主流程）。"""
    try:
        from db.database import get_session
        from db.crud import save_message, save_slots
        db = get_session()
        try:
            save_message(db, st.session_state.session_id, role, content)
            # 每轮 assistant 回复后同步槽位
            if role == "assistant":
                save_slots(db, st.session_state.session_id, st.session_state.slots)
        finally:
            db.close()
    except Exception as e:
        logging.debug("消息持久化失败（不影响聊天体验）: %s", e)


init_session()

# ── #19: 密码认证门控 ─────────────────────────────────
if APP_PASSWORD and not st.session_state.authenticated:
    st.markdown("### 🔒 访问验证")
    st.markdown("请输入访问密码后使用本服务。")
    pw_input = st.text_input("访问密码", type="password", key="app_pw_input")
    if st.button("进入", use_container_width=True, disabled=not pw_input):
        if hmac.compare_digest(pw_input.encode(), APP_PASSWORD.encode()):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密码错误，请重试。")
    st.stop()

# 检查是否有可用的 API Key（环境变量 or 用户输入）
_env_api_key = os.environ.get("LLM_API_KEY", "")
_has_env_key = bool(_env_api_key) and _env_api_key != "sk-your-api-key-here"


def get_or_create_advisor():
    """获取或创建 advisor 实例（根据 API Key 是否可用）。"""
    if st.session_state.api_key_confirmed and st.session_state.user_api_key:
        # #8: 使用 key hash 做比较，避免存储完整 key 副本
        _key_hash = hash(st.session_state.user_api_key)
        if "advisor" not in st.session_state or st.session_state.get("_advisor_key_hash") != _key_hash:
            st.session_state.advisor = GaokaoAdvisor(
                api_key=st.session_state.user_api_key,
                slots=st.session_state.slots,
            )
            st.session_state._advisor_key_hash = _key_hash
    elif _has_env_key:
        if "advisor" not in st.session_state:
            # 显式传入 API 配置，确保 secrets.toml / .env 生效
            st.session_state.advisor = GaokaoAdvisor(
                api_key=_env_api_key,
                base_url=os.environ.get("LLM_BASE_URL", ""),
                model=os.environ.get("LLM_MODEL", ""),
                slots=st.session_state.slots,
            )
    else:
        return None
    return st.session_state.advisor


advisor = get_or_create_advisor()
msg_count = st.session_state.msg_count

# ── 顶部标题 ──────────────────────────────────────────
st.markdown(
    '<div class="main-title">'
    "<h1>🎓 高报Agent AI 高考志愿顾问</h1>"
    "<p>说话直、不绕弯 — 帮你科学填报志愿</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── 免责声明三件套之二：入口 banner（简洁一行，可展开） ──
with st.expander("⚠️ 免责声明（点击展开）", expanded=False):
    st.caption(
        "本服务基于公开数据与 AI 推理生成，仅供参考，不构成升学建议。"
        "最终志愿以高校官方招生章程、省考试院公布数据为准。"
        "请勿输入身份证号、真实姓名等敏感信息。"
    )


# ── 侧边栏 ────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 高报Agent AI 高考志愿顾问")
    st.markdown("---")

    # API Key 输入（仅当环境变量中没有 key 时显示，正常部署不会出现）
    if not _has_env_key:
        st.markdown("#### ⚙️ 需要配置 API Key")
        st.markdown(
            "应用尚未配置 AI 服务。\n\n"
            "**部署者**：请在 Streamlit Cloud 的 Settings → Secrets 中添加：\n"
            "```toml\nLLM_API_KEY = \"sk-你的key\"\n```\n"
            "或者你也可以临时在下方输入自己的 Key 来体验："
        )
        api_input = st.text_input(
            "临时 API Key",
            type="password",
            placeholder="sk-...",
            key="api_key_input",
        )
        if st.button("✅ 使用此 Key", use_container_width=True, disabled=not api_input):
            st.session_state.user_api_key = api_input
            st.session_state.api_key_confirmed = True
            if "advisor" in st.session_state:
                del st.session_state["advisor"]
            st.rerun()
        st.markdown("[免费获取 DeepSeek Key →](https://platform.deepseek.com)")
        st.markdown("---")

    st.markdown("**智能分析你的分数**，推荐最合适的冲、稳、保院校。")

    st.markdown("#### 💡 使用技巧")
    for tip in TIPS:
        st.markdown(f'<div class="tip-item">{tip}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # 槽位进度（使用 session 级的 slots）
    _slots = st.session_state.slots
    filled = sum(1 for v in _slots.values() if v["filled"])
    total = len(_slots)
    st.markdown(f"#### 📊 信息采集进度 ({filled}/{total})")
    dots = ""
    for k, v in _slots.items():
        cls = "slot-filled" if v["filled"] else "slot-empty"
        safe_label = html.escape(v["label"])
        safe_value = html.escape(v["value"] if v["filled"] else "未填")
        dots += f'<span class="slot-dot {cls}" title="{safe_label}: {safe_value}"></span>'
    st.markdown(f'<div class="slot-bar">{dots}</div>', unsafe_allow_html=True)

    for k, v in _slots.items():
        status = "✅" if v["filled"] else "⬜"
        val = v["value"] if v["filled"] else "未填"
        st.markdown(f"{status} {v['label']}: {html.escape(val)}")

    st.markdown("---")

    # 🎯 快速开始面板：分步引导新用户填写基础信息
    with st.expander("🚀 快速开始（3步填基础信息）", expanded=True):
        st.markdown("**填一次，下次不用再写**")

        # 步骤 1：选择省份
        provinces_list = PROVINCES
        current_province = st.session_state.slots["province"]["value"] if st.session_state.slots["province"]["filled"] else ""
        province_idx = provinces_list.index(current_province) + 1 if current_province in provinces_list else 0
        selected_province = st.selectbox(
            "1️⃣ 你的省份",
            options=["（请选择）"] + provinces_list,
            index=province_idx,
            key="onboard_province",
        )

        # 步骤 2：输入分数/位次
        col_score, col_rank = st.columns(2)
        with col_score:
            current_score = st.session_state.slots["score_rank"]["value"]
            score_default = ""
            if "分" in current_score:
                score_default = current_score.replace("分", "").strip()
            input_score = st.text_input(
                "2️⃣ 分数（选填）",
                value=score_default,
                placeholder="如 580",
                key="onboard_score",
            )
        with col_rank:
            current_rank = st.session_state.slots["score_rank"]["value"]
            rank_default = ""
            if "位次" in current_rank:
                rank_default = current_rank.replace("位次", "").strip()
            input_rank = st.text_input(
                "或位次",
                value=rank_default,
                placeholder="如 15000",
                key="onboard_rank",
            )

        # 步骤 3：核心诉求（多选标签）
        st.markdown("3️⃣ 你最在意什么？（可多选）")
        goals_options = ["就业", "考公", "考研", "稳定", "高薪", "离家近", "大城市", "行业资源"]
        selected_goals = st.multiselect(
            "选择 1-3 个最核心的目标",
            options=goals_options,
            default=[],
            key="onboard_goals",
            label_visibility="collapsed",
        )

        # 提交按钮
        if st.button("✅ 一键填入，开始咨询", use_container_width=True):
            updated = []
            # 更新省份
            if selected_province and selected_province != "（请选择）":
                st.session_state.slots["province"]["value"] = selected_province
                st.session_state.slots["province"]["filled"] = True
                updated.append(f"省份={selected_province}")
            # 更新分数/位次（优先分数，如果有位次也一并记录）
            if input_score and input_score.strip().isdigit():
                rank_suffix = f"/位次{input_rank.strip()}" if (input_rank and input_rank.strip().isdigit()) else ""
                st.session_state.slots["score_rank"]["value"] = f"{input_score.strip()}分{rank_suffix}"
                st.session_state.slots["score_rank"]["filled"] = True
                updated.append(f"分数={input_score.strip()}")
            elif input_rank and input_rank.strip().isdigit():
                st.session_state.slots["score_rank"]["value"] = f"位次{input_rank.strip()}"
                st.session_state.slots["score_rank"]["filled"] = True
                updated.append(f"位次={input_rank.strip()}")
            # 更新目标
            if selected_goals:
                goals_text = "、".join(selected_goals)
                st.session_state.slots["goal"]["value"] = goals_text
                st.session_state.slots["goal"]["filled"] = True
                updated.append(f"目标={goals_text}")

            if updated:
                # 自动组装首条消息发给 AI
                intro_msg = "你好，我是" + (
                    st.session_state.slots["province"]["value"] or "（未填）"
                ) + "考生，"
                if st.session_state.slots["score_rank"]["filled"]:
                    intro_msg += st.session_state.slots["score_rank"]["value"] + "，"
                if st.session_state.slots["goal"]["filled"]:
                    intro_msg += "我比较在意" + st.session_state.slots["goal"]["value"] + "。"
                intro_msg += "请帮我分析一下志愿填报方向。"
                st.session_state["_quick_question"] = intro_msg
                st.success(f"已填入 {len(updated)} 项信息，开始咨询！")
                st.rerun()
            else:
                st.warning("请至少填写省份或分数中的一项。")

    st.markdown("---")

    # 📤 导出 & 分享
    with st.expander("📤 导出 & 分享", expanded=False):
        _sid = st.session_state.session_id
        st.markdown(
            f"**会话 ID**：`{_sid}`\n\n"
            f"关闭页面后，通过此链接可恢复对话：\n\n"
            f"页面地址栏中已包含 `?sid={_sid}`"
        )
        st.caption("💡 复制浏览器地址栏链接，发给家人或自己保存即可。")
        # 导出对话为 Markdown
        if st.button("📥 导出对话记录（Markdown）", use_container_width=True):
            export_lines = []
            export_lines.append(f"# AI 高考志愿顾问 — 对话记录")
            export_lines.append(f"**会话 ID**: {_sid}\n")
            # 槽位信息
            _slots = st.session_state.slots
            filled_slots = {k: v for k, v in _slots.items() if v["filled"]}
            if filled_slots:
                export_lines.append("## 已采集信息\n")
                for k, v in filled_slots.items():
                    export_lines.append(f"- **{v['label']}**: {v['value']}")
                export_lines.append("")
            export_lines.append("## 对话内容\n")
            for msg in st.session_state.messages:
                role_label = "👤 用户" if msg["role"] == "user" else "🤖 顾问"
                content = msg["content"]
                # 清理 HTML 标签
                content = re.sub(r'<[^>]+>', '', content)
                export_lines.append(f"### {role_label}\n{content}\n")
            export_text = "\n".join(export_lines)
            st.download_button(
                "💾 下载 Markdown 文件",
                data=export_text,
                file_name=f"高考志愿咨询记录_{_sid}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # P2-8: 导出志愿表 PDF
        _vt = st.session_state.get("_volunteer_table")
        if _vt and _vt.get("chong") or _vt and _vt.get("wen") or _vt and _vt.get("bao"):
            st.markdown("---")
            st.markdown("**📄 导出志愿表 PDF**")
            if st.button("📄 生成 PDF 志愿表", use_container_width=True, key="gen_pdf_btn"):
                try:
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib import colors
                    from reportlab.lib.units import cm
                    from reportlab.platypus import (
                        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                    )
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont

                    # 注册中文字体（尝试常见路径）
                    _font_paths = [
                        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                        "C:/Windows/Fonts/msyh.ttc",
                        "C:/Windows/Fonts/simsun.ttc",
                    ]
                    _font_name = "Helvetica"
                    for fp in _font_paths:
                        if os.path.exists(fp):
                            try:
                                pdfmetrics.registerFont(TTFont("ChineseFont", fp))
                                _font_name = "ChineseFont"
                                break
                            except Exception:
                                continue

                    import io
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(
                        buffer, pagesize=A4,
                        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                    )
                    styles = getSampleStyleSheet()
                    # 自定义样式
                    title_style = ParagraphStyle(
                        "PdfTitle", parent=styles["Title"],
                        fontName=_font_name, fontSize=16, spaceAfter=12,
                    )
                    normal_style = ParagraphStyle(
                        "PdfNormal", parent=styles["Normal"],
                        fontName=_font_name, fontSize=9, leading=13,
                    )
                    section_style = ParagraphStyle(
                        "PdfSection", parent=styles["Heading2"],
                        fontName=_font_name, fontSize=12, spaceBefore=10, spaceAfter=6,
                    )

                    elements = []

                    # 标题
                    elements.append(Paragraph("AI 高考志愿顾问 — 志愿表草案", title_style))
                    elements.append(Spacer(1, 6))

                    # 考生信息摘要
                    _slots = st.session_state.slots
                    info_parts = []
                    if _slots["province"]["filled"]:
                        info_parts.append(f"省份: {_slots['province']['value']}")
                    if _slots["score_rank"]["filled"]:
                        info_parts.append(f"分数/位次: {_slots['score_rank']['value']}")
                    if _slots["subject"]["filled"]:
                        info_parts.append(f"选科: {_slots['subject']['value']}")
                    if info_parts:
                        elements.append(Paragraph("考生信息：" + "  |  ".join(info_parts), normal_style))
                    if _vt.get("rank"):
                        elements.append(Paragraph(f"预估位次: {_vt['rank']:,}", normal_style))
                    elements.append(Spacer(1, 10))

                    # 冲/稳/保表格
                    for group_key, group_label in [
                        ("chong", "冲一冲（有风险但值得尝试）"),
                        ("wen", "稳一稳（主攻区，重点填报）"),
                        ("bao", "保一保（兜底，确保不掉档）"),
                    ]:
                        schools = _vt.get(group_key, [])
                        if not schools:
                            continue
                        elements.append(Paragraph(f"◆ {group_label}", section_style))
                        table_data = [["序号", "院校", "批次", "选科", "最低分", "最低位次"]]
                        for i, s in enumerate(schools, 1):
                            table_data.append([
                                str(i),
                                s.get("school_name", "?"),
                                s.get("batch", ""),
                                s.get("subject_type", ""),
                                str(s.get("min_score", "")),
                                str(s.get("min_rank", "")),
                            ])
                        t = Table(table_data, colWidths=[1.2*cm, 5*cm, 3*cm, 2.5*cm, 2.5*cm, 3*cm])
                        t.setStyle(TableStyle([
                            ("FONTNAME", (0, 0), (-1, -1), _font_name),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]))
                        elements.append(t)
                        elements.append(Spacer(1, 8))

                    # 数据来源说明
                    elements.append(Spacer(1, 12))
                    elements.append(Paragraph("数据来源说明", section_style))
                    elements.append(Paragraph(
                        "本志愿表数据来自教育部官方名单、各省教育考试院公开数据、"
                        "百度高考 API 等渠道。录取分数线为往年数据，仅供参考。",
                        normal_style,
                    ))

                    # 免责声明
                    elements.append(Spacer(1, 8))
                    elements.append(Paragraph("免责声明", section_style))
                    elements.append(Paragraph(
                        "本志愿表基于 AI 推理与往年数据生成，不构成升学建议。"
                        "最终填报请以各高校当年招生章程及省考试院公布的官方数据为准。"
                        "生成日期: 2026 年",
                        normal_style,
                    ))

                    doc.build(elements)
                    buffer.seek(0)
                    st.session_state["_pdf_bytes"] = buffer.getvalue()
                except ImportError:
                    st.error("PDF 生成需要 reportlab 库，请运行: pip install reportlab>=4.0")
                except Exception as e:
                    st.error(f"PDF 生成失败: {e}")

            # 如果已生成 PDF，提供下载按钮
            if st.session_state.get("_pdf_bytes"):
                st.download_button(
                    "💾 下载志愿表 PDF",
                    data=st.session_state["_pdf_bytes"],
                    file_name="志愿表草案.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

    st.markdown("---")

    # 📋 志愿表生成器
    with st.expander("📋 一键生成志愿表", expanded=False):
        st.markdown("**基于当前信息生成 2 冲 + 5 稳 + 3 保 的志愿表草案**")
        _slots_now = st.session_state.slots
        if not _slots_now["province"]["filled"] or not _slots_now["score_rank"]["filled"]:
            st.warning("请先在【快速开始】面板填好省份和分数。")
        else:
            # 选择数据年份
            _year = st.selectbox(
                "数据年份",
                options=[2024, 2023, 2022],
                index=0,
                key="vt_year",
                help="一般用最新一年的数据更准。",
            )
            # 选择选科（3+1+2 模式）
            _subj = st.selectbox(
                "选科类型",
                options=["物理", "历史"],
                index=0,
                key="vt_subj",
            )
            if st.button("📊 生成志愿表草案", use_container_width=True, type="primary"):
                try:
                    from gaokao_data import (
                        generate_volunteer_table,
                        format_volunteer_table,
                    )
                    # 解析分数
                    _score_text = _slots_now["score_rank"]["value"]
                    _score_match = re.search(r'(\d{3})', _score_text)
                    if _score_match:
                        _score = int(_score_match.group(1))
                        _table = generate_volunteer_table(
                            score=_score,
                            province=_slots_now["province"]["value"],
                            subject_type=_subj,
                            year=_year,
                        )
                        st.session_state["_volunteer_table"] = _table
                        st.success("志愿表已生成！请查看下方。")
                    else:
                        st.error("分数解析失败，请重新填写。")
                except Exception:
                    st.error("生成失败，请检查省份和分数是否正确。")

    st.markdown("---")

    # 重置按钮
    if st.button("🔄 重新开始对话", use_container_width=True):
        if advisor:
            advisor.reset()
        st.session_state.messages = []
        st.session_state.msg_count = 0
        st.session_state.limit_reached = False
        # 重置 slots
        for k in st.session_state.slots:
            st.session_state.slots[k]["filled"] = False
            st.session_state.slots[k]["value"] = ""
        st.rerun()

    st.markdown("---")

    # 💬 微信引流区块
    st.markdown("#### 💬 加入高考家长社区")

    st.markdown(
        '<div style="text-align:center; padding:0.6rem; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; margin:0.4rem 0;">'
        '<p style="font-size:0.9rem; color:#166534; margin:0; font-weight:600;">📱 高考家长交流群</p>'
        '<p style="font-size:0.75rem; color:#6b7280; margin:0.2rem 0;">500+ 家长在线交流志愿填报经验</p>'
        '<p style="font-size:0.7rem; color:#9ca3af; margin:0;">（群二维码请关注公众号获取）</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="text-align:center; padding:0.6rem; background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; margin:0.4rem 0;">'
        '<p style="font-size:0.9rem; color:#1e40af; margin:0; font-weight:600;">💬 关注公众号</p>'
        '<p style="font-size:0.75rem; color:#6b7280; margin:0.2rem 0;">最新高考政策解读 + 专业就业数据</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="text-align:center; padding:0.6rem; background:#fef3c7; border:1px solid #fde68a; border-radius:10px; margin:0.4rem 0;">'
        '<p style="font-size:0.9rem; color:#92400e; margin:0; font-weight:600;">📖 免费领取</p>'
        '<p style="font-size:0.75rem; color:#6b7280; margin:0.2rem 0;">《2026 志愿填报避坑指南》PDF</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ⭐ 品牌署名
    st.markdown(
        '<div style="text-align:center; padding:0.4rem; font-size:0.78rem; color:#9ca3af;">'
        '⭐ Powered by <b>雪峰Agent</b> · '
        '<a href="https://github.com" target="_blank" '
        'style="color:#3b82f6; text-decoration:none;">GitHub 开源</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        "**⚠️ 免责声明**\n\n"
        "本工具基于 AI 生成，**仅供参考**。\n\n"
        "志愿填报请以各省教育考试院、"
        "教育部阳光高考平台官方数据为准。"
    )


# ── 渲染历史消息 ───────────────────────────────────────
for msg_idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            # 解析并渲染学校卡片
            rendered = _render_school_cards(msg["content"])
            st.markdown(rendered, unsafe_allow_html=True)
            # 反馈按钮（P2-4）
            _fb_key = f"fb_{msg_idx}"
            _fb_val = st.session_state.get(f"_feedback_{msg_idx}")
            fb_cols = st.columns([1, 1, 8])
            with fb_cols[0]:
                _helpful_label = "👍 已赞" if _fb_val == "helpful" else "👍 有帮助"
                if st.button(_helpful_label, key=f"helpful_{_fb_key}", disabled=(_fb_val == "helpful")):
                    try:
                        from db.database import get_session as _gs
                        from db.crud import save_feedback as _sf
                        _db = _gs()
                        try:
                            _sf(_db, st.session_state.session_id, msg_idx, "helpful")
                        finally:
                            _db.close()
                    except Exception:
                        pass
                    st.session_state[f"_feedback_{msg_idx}"] = "helpful"
                    st.rerun()
            with fb_cols[1]:
                _unhelpful_label = "👎 已踩" if _fb_val == "not_helpful" else "👎 没帮助"
                if st.button(_unhelpful_label, key=f"not_helpful_{_fb_key}", disabled=(_fb_val == "not_helpful")):
                    try:
                        from db.database import get_session as _gs
                        from db.crud import save_feedback as _sf
                        _db = _gs()
                        try:
                            _sf(_db, st.session_state.session_id, msg_idx, "not_helpful")
                        finally:
                            _db.close()
                    except Exception:
                        pass
                    st.session_state[f"_feedback_{msg_idx}"] = "not_helpful"
                    st.rerun()
        else:
            st.markdown(msg["content"])

# ── 志愿表展示 ──
if st.session_state.get("_volunteer_table"):
    with st.chat_message("assistant"):
        st.markdown("### 📋 已生成你的专属志愿表草案")
        from gaokao_data import format_volunteer_table
        _table = st.session_state["_volunteer_table"]
        # 渲染为结构化卡片
        all_schools = []
        for g_key in ["chong", "wen", "bao"]:
            for s in _table.get(g_key, []):
                # 注入 group
                s2 = dict(s)
                s2["group"] = g_key
                s2["name"] = s2.get("school_name", "?")
                all_schools.append(s2)
        school_data_html = "<!--SCHOOL_DATA:" + _json.dumps(
            all_schools, ensure_ascii=False
        ) + "-->"
        rendered_html = _render_school_cards(school_data_html)
        st.markdown(rendered_html, unsafe_allow_html=True)
        # 文字部分
        text_part = format_volunteer_table(_table)
        st.markdown(text_part)
        # 操作按钮
        col1, col2 = st.columns(2)
        with col1:
            # 导出为文本
            st.download_button(
                "💾 下载志愿表（Markdown）",
                data=text_part,
                file_name="志愿表草案.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col2:
            if st.button("🗑️ 收起志愿表", use_container_width=True):
                st.session_state.pop("_volunteer_table", None)
                st.rerun()
        # 消费掉，避免重复渲染
        st.session_state.pop("_volunteer_table", None)


# ── 欢迎消息（仅首屏） ────────────────────────────────
_welcome_added = any("AI 高考志愿顾问" in m.get("content", "") for m in st.session_state.messages if m["role"] == "assistant")
if not _welcome_added:
    with st.chat_message("assistant"):
        # 免责声明三件套之三：对话首条消息末尾附简短提示
        st.markdown(WELCOME_MSG + "\n\n---\n" + DISCLAIMER_BRIEF)
    st.session_state.messages.append({
        "role": "assistant",
        "content": WELCOME_MSG + "\n\n---\n" + DISCLAIMER_BRIEF,
    })

# 快速提问按钮（始终显示，直到有用户消息）
_has_user_msg = any(m["role"] == "user" for m in st.session_state.messages)
if not _has_user_msg:
    cols = st.columns(2)
    for i, q in enumerate(QUICK_QUESTIONS):
        col = cols[i % 2]
        with col:
            if st.button(q, key=f"quick_{i}", use_container_width=True):
                st.session_state["_pending_question"] = q
                st.rerun()

# 快速提问 → 进入可编辑输入框（用户修改后再发送）
if "_pending_question" in st.session_state:
    _pending_q = st.session_state["_pending_question"]
    st.markdown(
        '<div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;'
        'padding:0.5rem 0.8rem;margin:0.4rem 0;font-size:0.85rem;color:#1e40af;">'
        '✏️ 以下问题已自动填入，你可以<b>修改补充</b>后再发送：</div>',
        unsafe_allow_html=True,
    )
    _edited = st.text_input(
        "编辑你的问题",
        value=_pending_q,
        key="_pending_question_input",
        label_visibility="collapsed",
    )
    c1, c2, _ = st.columns([1, 1, 5])
    with c1:
        _send_clicked = st.button("✅ 发送", use_container_width=True, type="primary")
    with c2:
        _cancel_clicked = st.button("❌ 取消", use_container_width=True)
    if _send_clicked and _edited.strip():
        user_input = _edited.strip()
        del st.session_state["_pending_question"]
    elif _cancel_clicked:
        del st.session_state["_pending_question"]
        st.rerun()
    else:
        user_input = None
else:
    user_input = None

# 聊天输入（无快速提问时显示）
if not user_input and "_pending_question" not in st.session_state:
    user_input = st.chat_input("输入你的情况，例如：我是山东考生，580分...")

if user_input:
    # 限流检查（IP 维度）
    client_ip = "unknown"
    try:
        ctx = st.context.headers
        client_ip = ctx.get("X-Forwarded-For", "").split(",")[0].strip() or \
                    ctx.get("X-Real-IP", "unknown")
    except Exception:
        client_ip = "unknown"  # IP 获取失败时降级

    _limiter = _GLOBAL_RATE_LIMITER
    allowed, reason = _limiter.check(client_ip, msg_length=len(user_input))

    if not allowed and reason == "input_too_long":
        st.warning(f"⚠️ 消息太长啦，请精简到 500 字以内（当前 {len(user_input)} 字）")
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.stop()
    elif not allowed:
        st.error("⏰ 今日免费额度已用完，明天再来吧～\n\n如需不限次数，可联系作者升级 VIP。")
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.limit_reached = True
        st.stop()

    # 检查是否有 API Key
    if not advisor:
        no_key_msg = "请先在左侧边栏输入你的 **API Key** 才能使用顾问。\n\n免费获取：[DeepSeek Platform](https://platform.deepseek.com)"
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            st.markdown(no_key_msg)
        st.session_state.messages.append({"role": "assistant", "content": no_key_msg})
        st.stop()

    # #10: 频率限制检查
    now = time.time()
    if now - st.session_state.last_request_time < MIN_REQUEST_INTERVAL:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        rate_msg = "请稍等一下再发送消息，操作太频繁了。"
        with st.chat_message("assistant"):
            st.markdown(rate_msg)
        st.session_state.messages.append({"role": "assistant", "content": rate_msg})
        st.stop()
    if st.session_state.msg_count >= MAX_MSG_PER_SESSION:
        with st.chat_message("assistant"):
            st.markdown("本次会话消息数已达上限，请点击「重新开始对话」。")
        st.stop()
    st.session_state.last_request_time = now

    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    _save_message_to_db("user", user_input)  # P3: 持久化

    # 处理指令：/reset
    if user_input.strip().lower() == "/reset":
        advisor.reset()
        for k in st.session_state.slots:
            st.session_state.slots[k]["filled"] = False
            st.session_state.slots[k]["value"] = ""
        reset_msg = "✅ 已重置对话和信息采集，我们可以重新开始。"
        with st.chat_message("assistant"):
            st.markdown(reset_msg)
        st.session_state.messages.append({"role": "assistant", "content": reset_msg})
        st.session_state.msg_count = 0
        st.session_state.limit_reached = False
        st.stop()

    # 处理指令：/slots
    if user_input.strip().lower() == "/slots":
        _slots_text = slots_summary(st.session_state.slots)
        with st.chat_message("assistant"):
            st.markdown(f"```\n{_slots_text}\n```")
        st.session_state.messages.append(
            {"role": "assistant", "content": f"```\n{_slots_text}\n```"}
        )
        st.stop()

    # ── 数据脱敏 & 隐私守卫：检测到敏感信息时，警告用户并阻断发送到 LLM ──
    _sensitive_hits = detect_sensitive_info(user_input)
    if _sensitive_hits:
        # 把检测到的敏感字符串用 **** 屏蔽（仅 UI 显示用）
        _sanitized_display = user_input
        for _kind, _pat in [
            ("身份证号", _RE_ID_CARD),
            ("手机号", _RE_MOBILE),
            ("银行卡号", _RE_BANK),
            ("QQ号", _RE_QQ),
            ("微信号", _RE_WECHAT),
            ("家庭住址", _RE_ADDRESS),
        ]:
            _sanitized_display = _pat.sub(f"**[**{_kind}已屏蔽**]**", _sanitized_display)
        # 真实姓名用"**"占位替换
        _sanitized_display = _RE_REAL_NAME.sub(
            r'\1**', _sanitized_display
        )
        # 修正最后一次 "user" 消息的展示（不显示原文）
        if st.session_state.messages and st.session_state.messages[-1].get("role") == "user":
            st.session_state.messages[-1]["content"] = _sanitized_display
        _warn_msg = SENSITIVE_WARNING.format(kinds="、".join(_sensitive_hits))
        with st.chat_message("assistant"):
            st.markdown(_warn_msg)
        st.session_state.messages.append({"role": "assistant", "content": _warn_msg})
        # 阻断：不再调用 advisor.chat()
        st.stop()

    # 调用 agent 核心逻辑（流式输出）
    with st.chat_message("assistant"):
        # 初始加载提示
        loading_placeholder = st.empty()
        loading_placeholder.markdown(
            '<div class="loading-step">🔍 正在分析你的信息...</div>',
            unsafe_allow_html=True,
        )

        reply = ""
        collected_chunks = []
        _stream_placeholder = None
        try:
            # 流式渲染：逐 chunk 输出到页面
            for chunk in advisor.chat_stream(user_input):
                if chunk.startswith("|||FINAL|||"):
                    # 最终标记：取出完整回复（后处理已在 chat_stream 内完成）
                    reply = chunk[len("|||FINAL|||"):]
                else:
                    # 首个 chunk 到达时清除加载提示
                    if not collected_chunks:
                        loading_placeholder.empty()
                    collected_chunks.append(chunk)
                    # 逐块刷新：第一个 chunk 时创建输出容器，后续追加
                    if len(collected_chunks) == 1:
                        _stream_placeholder = st.empty()
                    _stream_placeholder.markdown("".join(collected_chunks))

            # 如果流式过程中没收到任何 chunk（异常情况），用完整 reply 兜底
            if not reply and collected_chunks:
                reply = "".join(collected_chunks)

        except Exception as e:
            import traceback, logging
            logging.error("advisor.chat_stream failed: %s: %s", type(e).__name__, e, exc_info=True)
            reply = (
                "抱歉，AI 服务暂时遇到了问题，请稍后再试。\n\n"
                "如果持续出现这个问题，请检查 API 配置是否正确。"
            )
            loading_placeholder.empty()

        # ── 报告结尾免责声明（每轮 AI 回复后追加，确保用户始终看到合规提示）──
        # 检测是否包含「冲稳保」「推荐」「志愿表」等关键词，属于"报告"性质
        report_keywords = ("冲稳保", "推荐", "志愿表", "建议填报", "院校推荐", "专业推荐", "方案")
        disclaimer_appended = False
        if any(kw in reply for kw in report_keywords):
            reply = reply + "\n\n---\n" + DISCLAIMER_BRIEF
            disclaimer_appended = True

        # 流式渲染的是纯文本；完整回复拿到后，重新渲染一次（含学校卡片 + 免责声明）
        # 清除流式占位，用最终渲染替换
        if collected_chunks and _stream_placeholder is not None:
            _stream_placeholder.empty()
        # 解析并渲染学校卡片（需要完整文本才能解析 JSON）
        rendered = _render_school_cards(reply)
        st.markdown(rendered, unsafe_allow_html=True)

        # 反馈按钮（P2-4）— 新回复
        _new_fb_idx = len(st.session_state.messages)  # 即将追加的 assistant 消息的 index
        _fb_val_new = st.session_state.get(f"_feedback_{_new_fb_idx}")
        fb_cols_new = st.columns([1, 1, 8])
        with fb_cols_new[0]:
            _helpful_new = "👍 已赞" if _fb_val_new == "helpful" else "👍 有帮助"
            if st.button(_helpful_new, key=f"helpful_new_{_new_fb_idx}", disabled=(_fb_val_new == "helpful")):
                try:
                    from db.database import get_session as _gs
                    from db.crud import save_feedback as _sf
                    _db = _gs()
                    try:
                        _sf(_db, st.session_state.session_id, _new_fb_idx, "helpful")
                    finally:
                        _db.close()
                except Exception:
                    pass
                st.session_state[f"_feedback_{_new_fb_idx}"] = "helpful"
                st.rerun()
        with fb_cols_new[1]:
            _unhelpful_new = "👎 已踩" if _fb_val_new == "not_helpful" else "👎 没帮助"
            if st.button(_unhelpful_new, key=f"not_helpful_new_{_new_fb_idx}", disabled=(_fb_val_new == "not_helpful")):
                try:
                    from db.database import get_session as _gs
                    from db.crud import save_feedback as _sf
                    _db = _gs()
                    try:
                        _sf(_db, st.session_state.session_id, _new_fb_idx, "not_helpful")
                    finally:
                        _db.close()
                except Exception:
                    pass
                st.session_state[f"_feedback_{_new_fb_idx}"] = "not_helpful"
                st.rerun()

    st.session_state.messages.append({"role": "assistant", "content": reply})
    _save_message_to_db("assistant", reply)  # P3: 持久化

    # 更新计数器
    st.session_state.msg_count += 1
    # 清理快速提问编辑状态
    st.session_state.pop("_pending_question", None)
