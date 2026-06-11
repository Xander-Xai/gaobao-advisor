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
if hasattr(st, "secrets"):
    for key in ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_PROVIDER",
                "ENABLE_SEARCH"]:
        val = st.secrets.get(key)
        if val:
            os.environ[key] = str(val)

# 确保当前目录在 path 中，以便导入 agent 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import (
    GaokaoAdvisor,
    resolve_config,
    slots_summary,
    filled_slots,
    SLOTS,
)

# ── 常量 ─────────────────────────────────────────────
FREE_LIMIT = 3
UPGRADE_LINK = "#"  # 付费链接占位

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
    if "advisor" not in st.session_state:
        st.session_state.advisor = GaokaoAdvisor()
    if "msg_count" not in st.session_state:
        st.session_state.msg_count = 0
    if "messages" not in st.session_state:
        # messages 用于存储 Streamlit 聊天 UI 的显示记录
        st.session_state.messages = []
    if "limit_reached" not in st.session_state:
        st.session_state.limit_reached = False


init_session()

# 取出实例
advisor = st.session_state.advisor
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

    st.markdown("**智能分析你的分数**，推荐最合适的冲、稳、保院校。")

    st.markdown("#### 💡 使用技巧")
    for tip in TIPS:
        st.markdown(f'<div class="tip-item">{tip}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # 槽位进度
    filled = len(filled_slots())
    total = len(SLOTS)
    st.markdown(f"#### 📊 信息采集进度 ({filled}/{total})")
    dots = ""
    for k, v in SLOTS.items():
        cls = "slot-filled" if v["filled"] else "slot-empty"
        dots += f'<span class="slot-dot {cls}" title="{v["label"]}: {v["value"] if v["filled"] else "未填"}"></span>'
    st.markdown(f'<div class="slot-bar">{dots}</div>', unsafe_allow_html=True)

    for k, v in SLOTS.items():
        status = "✅" if v["filled"] else "⬜"
        val = v["value"] if v["filled"] else "未填"
        st.markdown(f"{status} {v['label']}: {val}")

    st.markdown("---")

    # 免费次数显示
    remaining = max(0, FREE_LIMIT - msg_count)
    if remaining > 1:
        badge_cls = "counter-ok"
        counter_text = f"✅ 剩余免费次数：{remaining} 次"
    elif remaining == 1:
        badge_cls = "counter-warn"
        counter_text = f"⚠️ 仅剩最后 1 次免费机会"
    else:
        badge_cls = "counter-limit"
        counter_text = "❌ 免费次数已用完"
    st.markdown(
        f'<div class="counter-badge {badge_cls}">{counter_text}</div>',
        unsafe_allow_html=True,
    )

    # 升级提示
    if msg_count >= FREE_LIMIT:
        st.markdown(
            '<div class="upgrade-box">'
            "<strong>🚀 解锁完整版</strong><br>"
            "无限对话 + 深度分析 + 志愿方案导出<br>"
            f'<a href="{UPGRADE_LINK}">立即升级</a>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 重置按钮
    if st.button("🔄 重新开始对话", use_container_width=True):
        advisor.reset()
        st.session_state.messages = []
        st.session_state.msg_count = 0
        st.session_state.limit_reached = False
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
    # 检查是否达到免费限制
    if msg_count >= FREE_LIMIT:
        st.session_state.limit_reached = True
        # 显示用户的输入（让用户看到自己发了什么）
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # 显示升级提示作为回复
        upgrade_msg = (
            "抱歉，你今天的 **免费咨询次数已用完** 😔\n\n"
            "升级到完整版即可享受：\n"
            "- ♾️ **无限对话**，不设次数限制\n"
            "- 📊 **深度院校分析**，包含录取概率评估\n"
            "- 📄 **志愿方案导出**，一键生成填报表\n"
            "- 🔍 **实时数据搜索**，获取最新分数线\n\n"
            f"[👉 点击这里升级]({UPGRADE_LINK})"
        )
        with st.chat_message("assistant"):
            st.markdown(upgrade_msg)
        st.session_state.messages.append({"role": "assistant", "content": upgrade_msg})
        st.stop()

    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 处理指令：/reset
    if user_input.strip().lower() == "/reset":
        advisor.reset()
        reset_msg = "✅ 已重置对话和信息采集，我们可以重新开始。"
        with st.chat_message("assistant"):
            st.markdown(reset_msg)
        st.session_state.messages.append({"role": "assistant", "content": reset_msg})
        st.session_state.msg_count = 0
        st.session_state.limit_reached = False
        st.stop()

    # 处理指令：/slots
    if user_input.strip().lower() == "/slots":
        with st.chat_message("assistant"):
            st.markdown(f"```\n{slots_summary()}\n```")
        st.session_state.messages.append(
            {"role": "assistant", "content": f"```\n{slots_summary()}\n```"}
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
