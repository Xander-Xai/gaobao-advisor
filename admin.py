#!/usr/bin/env python3
"""
高报Agent · 运营看板 (Admin Dashboard)
独立 Streamlit 页面，密码保护，展示运营数据。
Usage:
  ADMIN_PASSWORD=your_password streamlit run admin.py
"""

import json
import os
import hmac
from collections import Counter
from datetime import datetime, timedelta, date

import streamlit as st

# ── 页面配置（必须是第一个 st 命令）────────────────────
st.set_page_config(
    page_title="高报Agent 运营看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 常量 ─────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# 7 个槽位（与 app.py 保持一致）
SLOT_KEYS = [
    ("province", "省份"),
    ("score_rank", "分数/位次"),
    ("subject", "选科"),
    ("interest", "专业兴趣"),
    ("region", "地域偏好"),
    ("family", "家庭资源"),
    ("goal", "核心诉求"),
]

# 全国省份列表（用于从消息中提取省份关键词）
PROVINCES = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "广西", "海南",
    "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古",
]

# 常见专业关键词（用于从消息中提取）
MAJOR_KEYWORDS = [
    "计算机", "软件工程", "人工智能", "电子信息", "通信工程",
    "电气工程", "自动化", "机械", "土木", "建筑",
    "临床医学", "口腔", "护理", "药学", "中医",
    "金融", "经济学", "会计", "法学", "汉语言",
    "英语", "新闻", "传媒", "教育学", "心理学",
    "数学", "物理", "化学", "生物",
    "管理", "市场营销", "人力资源",
    "信息安全", "网络工程", "数据科学",
    "航空航天", "船舶", "核工程",
    "师范", "公安", "军校",
]


# ═══════════════════════════════════════════════════════
# 数据加载层
# ═══════════════════════════════════════════════════════


def _get_db_paths():
    """返回 analytics.db 和 gaokao.db 的绝对路径。"""
    base = os.path.dirname(os.path.abspath(__file__))
    analytics_db = os.path.join(base, "data", "analytics.db")
    gaokao_db = os.path.join(base, "data", "gaokao.db")
    return analytics_db, gaokao_db


def _load_from_analytics_db(date_from: date, date_to: date) -> dict:
    """从 analytics.db 的 events 表加载数据。"""
    import sqlite3

    analytics_db, _ = _get_db_paths()
    if not os.path.exists(analytics_db):
        return {}

    conn = sqlite3.connect(analytics_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 检查 events 表是否存在
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    ).fetchall()]
    if not tables:
        conn.close()
        return {}

    # 日期范围（UTC 字符串比较）
    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    ts_from = dt_from.strftime("%Y-%m-%d %H:%M:%S")
    ts_to = dt_to.strftime("%Y-%m-%d %H:%M:%S")

    params = {"ts_from": ts_from, "ts_to": ts_to}

    # 会话数（按天）
    cur.execute(
        "SELECT DATE(created_at) AS d, COUNT(DISTINCT session_id) AS cnt "
        "FROM events WHERE created_at >= :ts_from AND created_at < :ts_to "
        "AND event_type = 'session_start' GROUP BY d ORDER BY d",
        params,
    )
    daily_sessions = {r["d"]: r["cnt"] for r in cur.fetchall()}

    # 情绪分布
    cur.execute(
        "SELECT event_data FROM events "
        "WHERE event_type = 'emotion_detected' "
        "AND created_at >= :ts_from AND created_at < :ts_to",
        params,
    )
    emotion_dist = {"positive": 0, "neutral": 0, "negative": 0}
    for (data_json,) in cur.fetchall():
        if not data_json:
            continue
        try:
            data = json.loads(data_json)
            level = data.get("level", "")
            if level in ("🟢",):
                emotion_dist["positive"] += 1
            elif level in ("🔴",):
                emotion_dist["negative"] += 1
            else:
                emotion_dist["neutral"] += 1
        except (json.JSONDecodeError, TypeError):
            continue

    # 槽位填充
    cur.execute(
        "SELECT event_data FROM events "
        "WHERE event_type = 'slot_filled' "
        "AND created_at >= :ts_from AND created_at < :ts_to",
        params,
    )
    slot_counter = Counter()
    for (data_json,) in cur.fetchall():
        if not data_json:
            continue
        try:
            data = json.loads(data_json)
            slot_type = data.get("slot_type", "")
            if slot_type:
                slot_counter[slot_type] += 1
        except (json.JSONDecodeError, TypeError):
            continue

    # 事件类型分布
    cur.execute(
        "SELECT event_type, COUNT(*) AS cnt FROM events "
        "WHERE created_at >= :ts_from AND created_at < :ts_to "
        "GROUP BY event_type ORDER BY cnt DESC",
        params,
    )
    event_counts = {r["event_type"]: r["cnt"] for r in cur.fetchall()}

    # 总会话数 / 总消息数
    cur.execute(
        "SELECT COUNT(DISTINCT session_id) FROM events "
        "WHERE created_at >= :ts_from AND created_at < :ts_to",
        params,
    )
    total_sessions = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM events "
        "WHERE created_at >= :ts_from AND created_at < :ts_to",
        params,
    )
    total_events = cur.fetchone()[0]

    conn.close()

    return {
        "source": "analytics",
        "daily_sessions": daily_sessions,
        "emotion_dist": emotion_dist,
        "slot_counter": slot_counter,
        "event_counts": event_counts,
        "total_sessions": total_sessions,
        "total_events": total_events,
    }


def _load_from_gaokao_db(date_from: date, date_to: date) -> dict:
    """从 gaokao.db 的 conversations 和 conversation_messages 表加载数据。"""
    import sqlite3

    _, gaokao_db = _get_db_paths()
    if not os.path.exists(gaokao_db):
        return {}

    conn = sqlite3.connect(gaokao_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 检查 conversations 表是否存在
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    ).fetchall()]
    if not tables:
        conn.close()
        return {}

    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    ts_from = dt_from.strftime("%Y-%m-%d %H:%M:%S")
    ts_to = dt_to.strftime("%Y-%m-%d %H:%M:%S")
    params = {"ts_from": ts_from, "ts_to": ts_to}

    # 会话数（按天）
    cur.execute(
        "SELECT DATE(created_at) AS d, COUNT(*) AS cnt "
        "FROM conversations WHERE created_at >= :ts_from AND created_at < :ts_to "
        "GROUP BY d ORDER BY d",
        params,
    )
    daily_sessions = {r["d"]: r["cnt"] for r in cur.fetchall()}

    # 消息数（按天，按角色）
    cur.execute(
        "SELECT DATE(cm.created_at) AS d, cm.role, COUNT(*) AS cnt "
        "FROM conversation_messages cm "
        "JOIN conversations c ON cm.conversation_id = c.id "
        "WHERE cm.created_at >= :ts_from AND cm.created_at < :ts_to "
        "GROUP BY d, cm.role ORDER BY d",
        params,
    )
    daily_messages = {}
    role_counts = {"user": 0, "assistant": 0}
    for r in cur.fetchall():
        d = r["d"]
        role = r["role"]
        cnt = r["cnt"]
        if d not in daily_messages:
            daily_messages[d] = {"user": 0, "assistant": 0}
        daily_messages[d][role] = cnt
        role_counts[role] = role_counts.get(role, 0) + cnt

    # 所有用户消息（用于省份/专业提取）
    cur.execute(
        "SELECT cm.content FROM conversation_messages cm "
        "JOIN conversations c ON cm.conversation_id = c.id "
        "WHERE cm.role = 'user' "
        "AND cm.created_at >= :ts_from AND cm.created_at < :ts_to",
        params,
    )
    user_messages = [r["content"] for r in cur.fetchall()]

    # 槽位填充率（从 conversations.slots_json 中提取）
    cur.execute(
        "SELECT slots_json FROM conversations "
        "WHERE created_at >= :ts_from AND created_at < :ts_to "
        "AND slots_json IS NOT NULL",
        params,
    )
    slot_filled_counts = {k: 0 for k, _ in SLOT_KEYS}
    total_convs_with_slots = 0
    for (slots_json,) in cur.fetchall():
        if not slots_json:
            continue
        try:
            slots = json.loads(slots_json)
            total_convs_with_slots += 1
            for key, _ in SLOT_KEYS:
                slot_info = slots.get(key, {})
                if isinstance(slot_info, dict) and slot_info.get("filled"):
                    slot_filled_counts[key] += 1
        except (json.JSONDecodeError, TypeError):
            continue

    # 总会话数 / 总消息数
    cur.execute(
        "SELECT COUNT(*) FROM conversations "
        "WHERE created_at >= :ts_from AND created_at < :ts_to",
        params,
    )
    total_sessions = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM conversation_messages cm "
        "JOIN conversations c ON cm.conversation_id = c.id "
        "WHERE cm.created_at >= :ts_from AND cm.created_at < :ts_to",
        params,
    )
    total_messages = cur.fetchone()[0]

    conn.close()

    return {
        "source": "gaokao",
        "daily_sessions": daily_sessions,
        "daily_messages": daily_messages,
        "user_messages": user_messages,
        "slot_filled_counts": slot_filled_counts,
        "total_convs_with_slots": total_convs_with_slots,
        "role_counts": role_counts,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
    }


def _extract_provinces(messages: list[str]) -> list[str]:
    """从用户消息中提取省份名称。"""
    found = []
    for msg in messages:
        for p in PROVINCES:
            if p in msg:
                found.append(p)
    return found


def _extract_majors(messages: list[str]) -> list[str]:
    """从用户消息中提取专业关键词。"""
    found = []
    for msg in messages:
        for kw in MAJOR_KEYWORDS:
            if kw in msg:
                found.append(kw)
    return found


# ═══════════════════════════════════════════════════════
# 密码认证
# ═══════════════════════════════════════════════════════


def _check_password():
    """返回 True 如果密码正确或未设置密码。"""
    if not ADMIN_PASSWORD:
        return True

    if st.session_state.get("admin_authenticated"):
        return True

    st.markdown("## 🔒 运营看板 — 访问验证")
    st.markdown("请输入管理员密码以查看运营数据。")
    pw = st.text_input("管理员密码", type="password", key="admin_pw_input")
    if st.button("进入看板", disabled=not pw):
        if hmac.compare_digest(pw.encode(), ADMIN_PASSWORD.encode()):
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("密码错误，请重试。")
    st.stop()
    return False


# ═══════════════════════════════════════════════════════
# 主页面
# ═══════════════════════════════════════════════════════


def main():
    # 密码验证
    _check_password()

    # ── 页面标题 ──
    st.markdown(
        '<div style="text-align:center; padding:0.5rem 0 1rem 0;">'
        '<h1 style="margin:0; font-size:1.8rem;">📊 高报Agent 运营看板</h1>'
        '<p style="color:#6b7280; margin:0.2rem 0 0 0;">AI 高考志愿顾问 — 运营数据总览</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── 侧边栏：日期筛选 ──
    with st.sidebar:
        st.markdown("### 📅 日期筛选")
        today = date.today()
        default_from = today - timedelta(days=30)
        date_from = st.date_input("开始日期", value=default_from, key="date_from")
        date_to = st.date_input("结束日期", value=today, key="date_to")

        if date_from > date_to:
            st.error("开始日期不能晚于结束日期")
            st.stop()

        st.markdown("---")
        st.markdown("### 📋 数据来源")
        st.caption("优先从 analytics.db 的 events 表读取；若无则降级到 gaokao.db 的 conversations 表。")
        st.markdown("---")
        st.markdown(
            '<div style="text-align:center; font-size:0.78rem; color:#9ca3af;">'
            '⭐ Powered by <b>gaobao</b></div>',
            unsafe_allow_html=True,
        )

    # ── 加载数据 ──
    analytics_data = _load_from_analytics_db(date_from, date_to)
    gaokao_data = _load_from_gaokao_db(date_from, date_to)

    # 优先用 analytics.db，降级到 gaokao.db
    has_analytics = bool(analytics_data) and analytics_data.get("total_sessions", 0) > 0
    has_gaokao = bool(gaokao_data) and gaokao_data.get("total_sessions", 0) > 0

    if not has_analytics and not has_gaokao:
        st.info("所选日期范围内暂无数据。请先使用顾问产生一些对话数据。")
        st.stop()

    # ── 核心指标卡片 ──
    st.markdown("### 📈 核心指标")

    if has_analytics:
        data = analytics_data
        total_sessions = data["total_sessions"]
        total_events = data["total_events"]
        daily_sessions = data["daily_sessions"]

        # 今日 / 本周 会话数
        today_str = date.today().isoformat()
        today_sessions = daily_sessions.get(today_str, 0)

        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        week_sessions = sum(
            cnt for d, cnt in daily_sessions.items() if d >= week_start
        )

        # 平均每会话事件数
        avg_events = round(total_events / total_sessions, 1) if total_sessions > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("今日会话", today_sessions)
        col2.metric("本周会话", week_sessions)
        col3.metric("总会话数", total_sessions)
        col4.metric("总事件数", total_events)
        col5.metric("平均事件/会话", avg_events)

    elif has_gaokao:
        data = gaokao_data
        total_sessions = data["total_sessions"]
        total_messages = data["total_messages"]
        role_counts = data["role_counts"]
        daily_sessions = data["daily_sessions"]
        daily_messages = data["daily_messages"]

        today_str = date.today().isoformat()
        today_sessions = daily_sessions.get(today_str, 0)
        today_user_msgs = daily_messages.get(today_str, {}).get("user", 0)

        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        week_sessions = sum(
            cnt for d, cnt in daily_sessions.items() if d >= week_start
        )
        week_messages = sum(
            sum(dm.values()) for d, dm in daily_messages.items() if d >= week_start
        )

        user_count = role_counts.get("user", 0)
        assistant_count = role_counts.get("assistant", 0)
        avg_msgs = round(total_messages / total_sessions, 1) if total_sessions > 0 else 0

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("今日会话", today_sessions)
        col2.metric("本周会话", week_sessions)
        col3.metric("总会话数", total_sessions)
        col4.metric("今日消息", today_user_msgs)
        col5.metric("本周消息", week_messages)
        col6.metric("平均消息/会话", avg_msgs)

    st.markdown("---")

    # ── 会话趋势图 ──
    st.markdown("### 📅 会话趋势")
    if has_analytics:
        daily = analytics_data["daily_sessions"]
    else:
        daily = gaokao_data["daily_sessions"]

    if daily:
        # 填充日期空隙
        d1 = date_from
        d2 = date_to
        all_dates = []
        current = d1
        while current <= d2:
            all_dates.append(current.isoformat())
            current += timedelta(days=1)

        chart_data = {d: daily.get(d, 0) for d in all_dates}
        st.bar_chart(chart_data)
    else:
        st.info("暂无会话数据。")

    st.markdown("---")

    # ── 热门查询 TOP 10 ──
    st.markdown("### 🔥 热门查询 TOP 10")
    col_province, col_major = st.columns(2)

    with col_province:
        st.markdown("#### 📍 热门省份 TOP 10")
        if has_gaokao and gaokao_data.get("user_messages"):
            provinces_found = _extract_provinces(gaokao_data["user_messages"])
            province_counter = Counter(provinces_found)
            top_provinces = province_counter.most_common(10)
            if top_provinces:
                prov_data = {p: cnt for p, cnt in top_provinces}
                st.bar_chart(prov_data)
                for rank, (p, cnt) in enumerate(top_provinces, 1):
                    st.markdown(f"**{rank}.** {p} — {cnt} 次")
            else:
                st.info("暂无省份数据。")
        elif has_analytics:
            st.info("analytics.db 中暂无省份数据，请通过 gaokao.db 的对话记录分析。")
        else:
            st.info("暂无数据。")

    with col_major:
        st.markdown("#### 🎓 热门专业 TOP 10")
        if has_gaokao and gaokao_data.get("user_messages"):
            majors_found = _extract_majors(gaokao_data["user_messages"])
            major_counter = Counter(majors_found)
            top_majors = major_counter.most_common(10)
            if top_majors:
                maj_data = {m: cnt for m, cnt in top_majors}
                st.bar_chart(maj_data)
                for rank, (m, cnt) in enumerate(top_majors, 1):
                    st.markdown(f"**{rank}.** {m} — {cnt} 次")
            else:
                st.info("暂无专业数据。")
        elif has_analytics:
            st.info("analytics.db 中暂无专业数据，请通过 gaokao.db 的对话记录分析。")
        else:
            st.info("暂无数据。")

    st.markdown("---")

    # ── 情绪分布 ──
    st.markdown("### 😊 情绪分布")
    if has_analytics and analytics_data.get("emotion_dist"):
        emo = analytics_data["emotion_dist"]
        total_emo = sum(emo.values())
        if total_emo > 0:
            col_chart, col_detail = st.columns([2, 1])
            with col_chart:
                # 柱状图展示
                emo_labels = {"正面": emo["positive"], "中性": emo["neutral"], "负面": emo["negative"]}
                st.bar_chart(emo_labels)
            with col_detail:
                st.markdown(f"**正面（平静/积极）**: {emo['positive']} ({emo['positive']/total_emo*100:.0f}%)")
                st.markdown(f"**中性（普通）**: {emo['neutral']} ({emo['neutral']/total_emo*100:.0f}%)")
                st.markdown(f"**负面（焦虑/紧张）**: {emo['negative']} ({emo['negative']/total_emo*100:.0f}%)")
                st.markdown(f"**总计**: {total_emo} 条情绪记录")
        else:
            st.info("暂无情绪数据。")
    elif has_gaokao:
        # 从用户消息中简单分析情绪关键词
        if gaokao_data.get("user_messages"):
            msgs = gaokao_data["user_messages"]
            anxiety_kw = ["焦虑", "担心", "怕", "着急", "紧张", "慌", "愁", "崩溃", "迷茫", "不理想"]
            positive_kw = ["开心", "高兴", "感谢", "谢谢", "满意", "不错", "太好了"]
            anxiety_count = sum(1 for m in msgs if any(k in m for k in anxiety_kw))
            positive_count = sum(1 for m in msgs if any(k in m for k in positive_kw))
            neutral_count = len(msgs) - anxiety_count - positive_count

            col_chart, col_detail = st.columns([2, 1])
            with col_chart:
                emo_labels = {"正面": positive_count, "中性": neutral_count, "焦虑/负面": anxiety_count}
                st.bar_chart(emo_labels)
            with col_detail:
                total = len(msgs)
                st.markdown(f"**正面**: {positive_count} ({positive_count/total*100:.0f}%)")
                st.markdown(f"**中性**: {neutral_count} ({neutral_count/total*100:.0f}%)")
                st.markdown(f"**焦虑/负面**: {anxiety_count} ({anxiety_count/total*100:.0f}%)")
                st.markdown(f"**总计**: {total} 条消息")
                st.caption("（基于关键词简单分析，analytics.db 有精确情绪分数）")
        else:
            st.info("暂无消息数据。")
    else:
        st.info("暂无情绪数据。")

    st.markdown("---")

    # ── 槽位填充率 ──
    st.markdown("### 📊 槽位填充率")
    if has_gaokao and gaokao_data.get("total_convs_with_slots", 0) > 0:
        slot_counts = gaokao_data["slot_filled_counts"]
        total_convs = gaokao_data["total_convs_with_slots"]
        slot_data = {}
        for key, label in SLOT_KEYS:
            count = slot_counts.get(key, 0)
            rate = round(count / total_convs * 100, 1) if total_convs > 0 else 0
            slot_data[label] = rate

        st.bar_chart(slot_data)

        # 详细表格
        col_a, col_b = st.columns([3, 1])
        with col_a:
            for key, label in SLOT_KEYS:
                count = slot_counts.get(key, 0)
                rate = count / total_convs * 100 if total_convs > 0 else 0
                st.markdown(f"**{label}**: {count}/{total_convs} ({rate:.0f}%)")
                st.progress(min(rate / 100, 1.0))
        with col_b:
            st.metric("已收集槽位会话", total_convs)

    elif has_analytics and analytics_data.get("slot_counter"):
        slot_counter = analytics_data["slot_counter"]
        # slot_counter 的 key 是 slot_type（如"家庭""诉求""兴趣"）
        slot_mapping = {
            "省份": "province", "分数": "score_rank", "位次": "score_rank",
            "选科": "subject", "兴趣": "interest", "专业": "interest",
            "地域": "region", "家庭": "family", "诉求": "goal",
        }
        slot_data = {}
        for slot_type, cnt in slot_counter.most_common():
            slot_data[slot_type] = cnt

        if slot_data:
            st.bar_chart(slot_data)
            for slot_type, cnt in slot_counter.most_common():
                st.markdown(f"**{slot_type}**: {cnt} 次填充")
        else:
            st.info("暂无槽位数据。")
    else:
        st.info("暂无槽位填充数据。")

    st.markdown("---")

    # ── 事件分布（仅 analytics.db）──
    if has_analytics and analytics_data.get("event_counts"):
        st.markdown("### 📋 事件类型分布")
        event_counts = analytics_data["event_counts"]
        event_labels = {
            k: v for k, v in sorted(event_counts.items(), key=lambda x: -x[1])
        }
        st.bar_chart(event_labels)
        for event_type, cnt in event_labels.items():
            st.markdown(f"- **{event_type}**: {cnt} 次")

    st.markdown("---")

    # ── 用户反馈（P2-4）──
    st.markdown("### 👍 用户反馈")
    _, gaokao_db_path = _get_db_paths()
    if os.path.exists(gaokao_db_path):
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(gaokao_db_path)
        _cur = _conn.cursor()
        # 检查 feedbacks 表是否存在
        _tables = [r[0] for r in _cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feedbacks'"
        ).fetchall()]
        if _tables:
            _cur.execute("SELECT COUNT(*) FROM feedbacks WHERE rating = 'helpful'")
            _fb_helpful = _cur.fetchone()[0]
            _cur.execute("SELECT COUNT(*) FROM feedbacks WHERE rating = 'not_helpful'")
            _fb_not_helpful = _cur.fetchone()[0]
            _fb_total = _fb_helpful + _fb_not_helpful
            _fb_rate = f"{_fb_helpful / _fb_total * 100:.1f}%" if _fb_total > 0 else "N/A"

            fb_col1, fb_col2, fb_col3, fb_col4 = st.columns(4)
            fb_col1.metric("总反馈数", _fb_total)
            fb_col2.metric("有帮助", _fb_helpful)
            fb_col3.metric("没帮助", _fb_not_helpful)
            fb_col4.metric("好评率", _fb_rate)

            if _fb_total > 0:
                _fb_chart_data = {"有帮助": _fb_helpful, "没帮助": _fb_not_helpful}
                st.bar_chart(_fb_chart_data)

            # 最近反馈（按时间倒序）
            _cur.execute(
                "SELECT session_id, message_index, rating, created_at "
                "FROM feedbacks ORDER BY created_at DESC LIMIT 10"
            )
            _recent = _cur.fetchall()
            if _recent:
                st.markdown("#### 最近 10 条反馈")
                for _sid, _mi, _rating, _ts in _recent:
                    _emoji = "👍" if _rating == "helpful" else "👎"
                    _label = "有帮助" if _rating == "helpful" else "没帮助"
                    st.markdown(f"- {_emoji} **{_label}** | 会话 `{_sid[:8]}...` 消息#{_mi} | {_ts}")
        else:
            st.info("feedbacks 表暂无数据（表已创建，等待用户反馈）。")
        _conn.close()
    else:
        st.info("gaokao.db 不存在，无法展示反馈数据。")

    # ── 底部信息 ──
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; color:#9ca3af; font-size:0.78rem;">'
        f'数据范围: {date_from.isoformat()} ~ {date_to.isoformat()} | '
        f'数据来源: {"analytics.db (events)" if has_analytics else "gaokao.db (conversations)"} | '
        f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
