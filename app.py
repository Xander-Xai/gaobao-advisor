#!/usr/bin/env python3
"""
锐评 AI 高考志愿顾问 — Streamlit Web 前端
复用 agent.py 的核心逻辑，提供移动端友好的聊天界面。
Usage:
  streamlit run app.py
"""

import os
import sys
import time
import uuid
import html
import streamlit as st

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
)
from ratelimit import RateLimiter

# ── 常量 ─────────────────────────────────────────────

# #19: 应用级密码认证（通过环境变量 APP_PASSWORD 启用）
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

WELCOME_MSG = (
    "你好！我是 **锐评 AI 高考志愿顾问**，说话直、不绕弯，专门帮你解决志愿填报难题。\n\n"
    "我会根据你的 **省份、分数/位次、选科、兴趣方向** 等信息，"
    "结合 **就业、考研、考公、城市** 等目标，给出 **冲、稳、保** 的学校推荐。\n\n"
    "📌 **3 步开启咨询**：\n"
    "1️⃣ 点击下方【快速开始】，告诉我你的省份和分数\n"
    "2️⃣ 根据提示补充选科、兴趣方向、家庭情况\n"
    "3️⃣ 拿到专属的冲稳保推荐 + 志愿表建议\n\n"
    "👇 也可以直接输入自己的问题："
)

# 场景化快速提问（按用户类型分组，不限定具体省份）
QUICK_QUESTIONS = [
    "📍 我是[XX省]考生，想让你帮我分析",
    "🎯 我是高分考生，想冲 985/211",
    "💼 我想找好就业的专业，怎么选？",
    "📝 我想考公/考研，应该报什么？",
    "👨‍👩‍👧 家里有行业资源，怎么利用？",
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
# 银行卡号（16-19位连续数字，宽松匹配）
_RE_BANK = _re.compile(r'(?<!\d)\d{16,19}(?!\d)')
# 真实姓名启发式关键词 + 高考常用词黑名单（避免误判"我是山东考生"）
_REAL_NAME_BLOCKLIST = frozenset({
    "山东", "考生", "学生", "同学", "老师", "家长",
    "父母", "父亲", "母亲", "姐妹", "兄弟", "高三", "今年",
})
_RE_REAL_NAME = _re.compile(
    r'(?:我叫|我是|我儿子叫|我女儿叫|我同学叫|我朋友叫|考生姓名|姓名)'
    r'\s*([一-龥]{2,4})',
    _re.UNICODE
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
        hits.append("银行卡号")
    if _RE_REAL_NAME.search(text):
        # 二次过滤：排除高考场景常用词
        for m in _RE_REAL_NAME.finditer(text):
            name = m.group(1).strip()
            if name not in _REAL_NAME_BLOCKLIST:
                hits.append("真实姓名")
                break
    return hits


SENSITIVE_WARNING = (
    "🔒 **检测到敏感信息**\n\n"
    "你刚才的输入中包含 {kinds}。请不要在对话里输入任何真实个人信息。\n\n"
    "**为什么重要**：\n"
    "- 本服务不存储对话历史，但安全起见请勿输入\n"
    "- 涉及身份证/姓名/手机号属于《个人信息保护法》规制范围\n\n"
    "**建议**：\n"
    "- 改用「某同学」「考生A」等匿名代称\n"
    "- 分数、位次、选科、兴趣方向等都是非敏感信息，可以正常输入\n\n"
    "—— 我已经把你的敏感信息**自动从记忆中清除**，请重新输入你想问的问题。"
)


# ── 学校卡片渲染 ──
# 解析 agent 输出中的结构化数据标记 `<!--SCHOOL_DATA:...-->`
# 渲染为可视化的冲/稳/保卡片
import json as _json
import re as _re
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


def _render_school_cards(reply_text: str) -> str:
    """
    解析回复中的学校数据标记，渲染为卡片，剩余文本原样保留。
    支持两种格式：
    1. <!--SCHOOL_DATA:[{...},{...}]-->
    2. <!--SCHOOL_DATA:{...}-->  (单个学校)
    """
    def _replace(match):
        raw = match.group(1).strip()
        try:
            data = _json.loads(raw)
        except Exception:
            return match.group(0)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            return match.group(0)

        # 按 group 分组
        groups = {"chong": [], "wen": [], "bao": []}
        for s in data:
            g = str(s.get("group", "wen")).strip()
            if g not in groups:
                g = "wen"
            groups[g].append(s)

        parts = []
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
        return "".join(parts)

    return _SCHOOL_DATA_PATTERN.sub(_replace, reply_text)



# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="锐评 AI 高考志愿顾问",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

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
    # 进程级限流器（共享同一 RateLimiter 实例以保证 LRU 淘汰对所有 session 一致）
    if "_rate_limiter" not in st.session_state:
        st.session_state._rate_limiter = RateLimiter(
            hourly_limit=20,
            daily_limit=40,
            max_input_len=500,
        )
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
        if url_sid:
            st.session_state.session_id = url_sid
        else:
            st.session_state.session_id = uuid.uuid4().hex[:12]
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
    except Exception:
        pass  # 数据库不可用时静默失败


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
    except Exception:
        pass  # 持久化失败不影响聊天体验


init_session()

# ── #19: 密码认证门控 ─────────────────────────────────
if APP_PASSWORD and not st.session_state.authenticated:
    st.set_page_config(page_title="锐评 AI 高考志愿顾问 — 登录", page_icon="🔒", layout="centered")
    st.markdown("### 🔒 访问验证")
    st.markdown("请输入访问密码后使用本服务。")
    pw_input = st.text_input("访问密码", type="password", key="app_pw_input")
    if st.button("进入", use_container_width=True, disabled=not pw_input):
        if pw_input == APP_PASSWORD:
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
            st.session_state.advisor = GaokaoAdvisor(slots=st.session_state.slots)
    else:
        return None
    return st.session_state.advisor


advisor = get_or_create_advisor()
msg_count = st.session_state.msg_count

# ── 顶部标题 ──────────────────────────────────────────
st.markdown(
    '<div class="main-title">'
    "<h1>🎓 锐评 AI 高考志愿顾问</h1>"
    "<p>说话直、不绕弯 — 帮你科学填报志愿</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── 免责声明三件套之二：入口 banner（醒目黄色提示框） ──
st.markdown(
    '<div style="background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;'
    'padding:0.6rem 0.9rem;margin:0.4rem 0 0.8rem 0;font-size:0.82rem;color:#92400e;">'
    '⚠️ <b>免责声明</b>：本服务基于公开数据与 AI 推理生成，<b>仅供参考，不构成升学建议</b>。'
    '最终志愿以高校官方招生章程、省考试院公布数据为准。'
    '请勿输入身份证号、真实姓名等敏感信息。'
    '</div>',
    unsafe_allow_html=True,
)


# ── 侧边栏 ────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 锐评 AI 高考志愿顾问")
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
        st.markdown(f"{status} {v['label']}: {val}")

    st.markdown("---")

    # 🎯 快速开始面板：分步引导新用户填写基础信息
    with st.expander("🚀 快速开始（3步填基础信息）", expanded=False):
        st.markdown("**填一次，下次不用再写**")

        # 步骤 1：选择省份
        provinces_list = [
            "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
            "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
            "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
            "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆"
        ]
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
                try:
                    score_default = current_score.replace("分", "").strip()
                except:
                    pass
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
                try:
                    rank_default = current_rank.replace("位次", "").strip()
                except:
                    pass
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
            # 更新分数
            if input_score and input_score.strip().isdigit():
                st.session_state.slots["score_rank"]["value"] = f"{input_score.strip()}分"
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
        # 分享链接
        _base_url = st.query_params.get("sid", _sid)
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
                import re as _re3
                content = _re3.sub(r'<[^>]+>', '', content)
                export_lines.append(f"### {role_label}\n{content}\n")
            export_text = "\n".join(export_lines)
            st.download_button(
                "💾 下载 Markdown 文件",
                data=export_text,
                file_name=f"高考志愿咨询记录_{_sid}.md",
                mime="text/markdown",
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
                    import re as _re2
                    _score_match = _re2.search(r'(\d{3})', _score_text)
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
                except Exception as e:
                    st.error(f"生成失败：{e}")

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
    st.markdown(
        "**⚠️ 免责声明**\n\n"
        "本工具基于 AI 生成，**仅供参考**。\n\n"
        "志愿填报请以各省教育考试院、"
        "教育部阳光高考平台官方数据为准。"
    )


# ── 渲染历史消息 ───────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            # 解析并渲染学校卡片
            rendered = _render_school_cards(msg["content"])
            st.markdown(rendered, unsafe_allow_html=True)
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
if not st.session_state.messages:
    with st.chat_message("assistant"):
        # 免责声明三件套之三：对话首条消息末尾附简短提示
        st.markdown(WELCOME_MSG + "\n\n---\n" + DISCLAIMER_BRIEF)
        st.session_state.messages.append({
            "role": "assistant",
            "content": WELCOME_MSG + "\n\n---\n" + DISCLAIMER_BRIEF,
        })

    # 快速提问按钮
    cols = st.columns(2)
    for i, q in enumerate(QUICK_QUESTIONS):
        col = cols[i % 2]
        with col:
            if st.button(q, key=f"quick_{i}", use_container_width=True):
                # 将快速提问作为用户输入处理
                st.session_state["_quick_question"] = q
                st.rerun()

# 处理快速提问
if "_quick_question" in st.session_state:
    user_input = st.session_state.pop("_quick_question")
else:
    user_input = None

# 聊天输入（快速提问优先，否则用 chat_input）
if not user_input:
    user_input = st.chat_input("输入你的情况，例如：我是山东考生，580分...")

if user_input:
    # 限流检查（IP 维度）
    client_ip = "unknown"
    try:
        ctx = st.context.headers
        client_ip = ctx.get("X-Forwarded-For", "").split(",")[0].strip() or \
                    ctx.get("X-Real-IP", "unknown")
    except Exception:
        pass

    _limiter = st.session_state._rate_limiter
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

    # 调用 agent 核心逻辑
    with st.chat_message("assistant"):
        # 分阶段加载提示：根据耗时显示不同文案
        loading_placeholder = st.empty()
        loading_placeholder.markdown(
            '<div class="loading-step">🔍 正在分析你的信息...</div>',
            unsafe_allow_html=True,
        )
        import threading
        _stop_loading = threading.Event()

        def _show_loading_stages():
            """后台线程：分阶段切换提示文案。"""
            _stages = [
                (1.5, '🔍 正在匹配院校数据...'),
                (4.0, '🤖 AI 顾问正在分析，马上就好...'),
                (8.0, '💡 还在思考中... 复杂问题需要更长时间'),
            ]
            elapsed = 0.0
            for delay, text in _stages:
                wait_for = delay - elapsed
                if _stop_loading.wait(wait_for):
                    return
                elapsed = delay
                loading_placeholder.markdown(
                    f'<div class="loading-step">{text}</div>',
                    unsafe_allow_html=True,
                )

        _loader = threading.Thread(target=_show_loading_stages, daemon=True)
        _loader.start()
        try:
            reply = advisor.chat(user_input)
        except Exception as e:
            reply = (
                "抱歉，AI 服务暂时不可用，请稍后重试。\n\n"
                "如问题持续，请检查 API 配置是否正确。"
            )
        finally:
            _stop_loading.set()
            loading_placeholder.empty()
        # ── 报告结尾免责声明（每轮 AI 回复后追加，确保用户始终看到合规提示）──
        # 检测是否包含「冲稳保」「推荐」「志愿表」等关键词，属于"报告"性质
        report_keywords = ("冲稳保", "推荐", "志愿表", "建议填报", "院校推荐", "专业推荐", "方案")
        if any(kw in reply for kw in report_keywords):
            reply = reply + "\n\n---\n" + DISCLAIMER_BRIEF
        # 解析并渲染学校卡片
        rendered = _render_school_cards(reply)
        st.markdown(rendered, unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    _save_message_to_db("assistant", reply)  # P3: 持久化

    # 更新计数器
    st.session_state.msg_count += 1
