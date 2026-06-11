#!/usr/bin/env python3
"""
高考志愿顾问 — Streamlit Web 前端
复用 agent.py 的核心逻辑，提供移动端友好的聊天界面。
Usage:
  streamlit run app.py
"""

import os
import sys
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

# ── 常量 ─────────────────────────────────────────────

WELCOME_MSG = (
    "你好！我是 **AI 高考志愿顾问**，专门帮你解决志愿填报难题。\n\n"
    "你可以直接告诉我：\n"
    "- 你的 **省份、分数/位次**\n"
    "- 感兴趣的 **专业方向**（或讨厌的方向）\n"
    "- 对 **城市、就业、考研** 等方面的想法\n\n"
    "我会根据你的实际情况，给出 **冲、稳、保** 的学校推荐。\n\n"
    "👇 点击下方问题直接开始，或者自己输入："
)

# 快速提问示例（点击即可发送）
QUICK_QUESTIONS = [
    "我是湖北考生，580分，想学计算机",
    "河南文科510分，想考公务员",
    "家里在电力系统，河北600分怎么选",
    "380分只能上专科，还有出路吗",
    "金融专业到底能不能学",
    "高一选科，想学医怎么选",
]

TIPS = [
    "先说省份和分数，我能更快帮你分析",
    "可以说出喜欢/讨厌的专业方向",
    "告诉我你在意什么：就业、考研、城市、离家远近",
    "随时输入 `/reset` 重新开始对话",
]


# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="AI 高考志愿顾问",
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

    /* 隐藏 Streamlit 默认的 hamburger menu 和 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


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


init_session()

# 检查是否有可用的 API Key（环境变量 or 用户输入）
_env_api_key = os.environ.get("LLM_API_KEY", "")
_has_env_key = bool(_env_api_key) and _env_api_key != "sk-your-api-key-here"


def get_or_create_advisor():
    """获取或创建 advisor 实例（根据 API Key 是否可用）。"""
    if st.session_state.api_key_confirmed and st.session_state.user_api_key:
        if "advisor" not in st.session_state or st.session_state.get("_advisor_key") != st.session_state.user_api_key:
            st.session_state.advisor = GaokaoAdvisor(
                api_key=st.session_state.user_api_key,
                slots=st.session_state.slots,
            )
            st.session_state._advisor_key = st.session_state.user_api_key
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
    "<h1>🎓 AI 高考志愿顾问</h1>"
    "<p>基于大数据 + AI，帮你科学填报志愿</p>"
    "</div>",
    unsafe_allow_html=True,
)


# ── 侧边栏 ────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 免费 AI 高考志愿顾问")
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
        dots += f'<span class="slot-dot {cls}" title="{v["label"]}: {v["value"] if v["filled"] else "未填"}"></span>'
    st.markdown(f'<div class="slot-bar">{dots}</div>', unsafe_allow_html=True)

    for k, v in _slots.items():
        status = "✅" if v["filled"] else "⬜"
        val = v["value"] if v["filled"] else "未填"
        st.markdown(f"{status} {v['label']}: {val}")

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


# ── 渲染历史消息 ───────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── 欢迎消息（仅首屏） ────────────────────────────────
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(WELCOME_MSG)
        st.session_state.messages.append({"role": "assistant", "content": WELCOME_MSG})

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

    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

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

    # 调用 agent 核心逻辑
    with st.chat_message("assistant"):
        with st.spinner("正在分析中，请稍候..."):
            try:
                reply = advisor.chat(user_input)
            except Exception as e:
                reply = (
                    f"抱歉，处理时出现了问题：{e}\n\n"
                    "请检查 API 配置是否正确，或稍后重试。"
                )
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

    # 更新计数器
    st.session_state.msg_count += 1
