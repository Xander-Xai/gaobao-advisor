"""
3-step onboarding flow for first-time users.

Step 1: Province selection (grid of 30 provinces)
Step 2: Score input (0-900)
Step 3: Subject type + interest

Pure Python core (OnboardingState) with a Streamlit render_onboarding() function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from constants import PROVINCES

# ── Province modes (UI display — extended with traditional mode) ──
PROVINCE_MODES: dict[str, str] = {
    # 3+3 provinces
    "北京": "3+3",
    "天津": "3+3",
    "上海": "3+3",
    "山东": "3+3",
    "浙江": "3+3",
    "海南": "3+3",
    # 3+1+2 provinces
    "河北": "3+1+2",
    "辽宁": "3+1+2",
    "江苏": "3+1+2",
    "福建": "3+1+2",
    "湖北": "3+1+2",
    "湖南": "3+1+2",
    "广东": "3+1+2",
    "重庆": "3+1+2",
    "安徽": "3+1+2",
    "江西": "3+1+2",
    "贵州": "3+1+2",
    "广西": "3+1+2",
    "甘肃": "3+1+2",
    "黑龙江": "3+1+2",
    "吉林": "3+1+2",
    # Traditional provinces
    "山西": "传统文理",
    "河南": "传统文理",
    "四川": "传统文理",
    "云南": "传统文理",
    "陕西": "传统文理",
    "内蒙古": "传统文理",
    "西藏": "传统文理",
    "宁夏": "传统文理",
    "新疆": "传统文理",
    "青海": "传统文理",
}

# ── Subject & interest options ────────────────────────────

SUBJECT_TYPES: list[str] = [
    "物化生",
    "物化政",
    "物化地",
    "物生政",
    "物生地",
    "物政地",
    "史化政",
    "史化地",
    "史生政",
    "史生地",
    "史地政",
    "历史方向",
    "物理方向",
    "文科",
    "理科",
    "其他",
]

INTERESTS: list[str] = [
    "计算机/人工智能",
    "电子信息/通信",
    "医学/临床",
    "经济/金融",
    "法学",
    "师范/教育",
    "建筑/土木",
    "机械/自动化",
    "化学/材料",
    "生物/农学",
    "文学/新闻",
    "管理/工商",
    "艺术/设计",
    "暂不确定",
]


# ── OnboardingState dataclass ─────────────────────────────


@dataclass
class OnboardingState:
    """Tracks progress through the 3-step onboarding flow."""

    step: int = 1
    province: str | None = None
    score: int | None = None
    subject: str | None = None
    interest: str | None = None

    def is_complete(self) -> bool:
        """Return True when all three steps are filled."""
        return all(
            [
                self.province is not None,
                self.score is not None,
                self.subject is not None,
                self.interest is not None,
            ]
        )

    def should_skip(
        self,
        has_user_messages: bool,
        has_filled_slots: bool,
    ) -> bool:
        """Decide whether to skip onboarding entirely.

        Skip when:
        - User already has messages (has started chatting), OR
        - Slots are already filled (returning user / restored state).
        """
        return has_user_messages or has_filled_slots

    def set_province(self, province: str) -> None:
        """Set province and advance to step 2."""
        self.province = province
        self.step = 2

    def set_score(self, score: int) -> None:
        """Set score and advance to step 3."""
        self.score = score
        self.step = 3

    def set_subject(self, subject: str) -> None:
        """Set subject type."""
        self.subject = subject

    def set_interest(self, interest: str) -> None:
        """Set interest."""
        self.interest = interest

    def to_slots(self) -> dict[str, dict[str, Any]]:
        """Convert onboarding answers to the slot format used by agent.py."""
        slots: dict[str, dict[str, Any]] = {
            "province": {"label": "省份", "filled": False, "value": ""},
            "score_rank": {"label": "分数/位次", "filled": False, "value": ""},
            "subject": {"label": "选科", "filled": False, "value": ""},
            "interest": {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
            "region": {"label": "地域偏好", "filled": False, "value": ""},
            "family": {"label": "家庭资源", "filled": False, "value": ""},
            "goal": {"label": "核心诉求", "filled": False, "value": ""},
        }

        if self.province is not None:
            slots["province"]["filled"] = True
            slots["province"]["value"] = self.province

        if self.score is not None:
            slots["score_rank"]["filled"] = True
            slots["score_rank"]["value"] = self.score

        if self.subject is not None:
            slots["subject"]["filled"] = True
            slots["subject"]["value"] = self.subject

        if self.interest is not None:
            slots["interest"]["filled"] = True
            slots["interest"]["value"] = self.interest

        return slots


# ── Streamlit rendering ───────────────────────────────────


def render_onboarding() -> OnboardingState | None:
    """Render the 3-step onboarding cards in Streamlit.

    Returns:
        OnboardingState when all steps are complete (user clicked "开始咨询").
        None while the user is still going through the steps.
    """
    import streamlit as st

    state: OnboardingState = st.session_state.get("onboarding", OnboardingState())

    if state.step == 1:
        _render_step_province(state)
        return None

    if state.step == 2:
        _render_step_score(state)
        return None

    if state.step == 3 and not state.is_complete():
        _render_step_subject_interest(state)
        return None

    # All steps complete -- return state and persist to session
    st.session_state["onboarding"] = state
    return state


def _render_step_province(state: OnboardingState) -> None:
    """Step 1: Province selection grid."""
    import streamlit as st

    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        "<h3 style='margin-bottom:0.2rem;'>📍 第 1 步 / 共 3 步</h3>"
        "<p style='color:#666;font-size:0.9rem;'>选择你所在的省份</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    cols_per_row = 4
    provinces_sorted = sorted(PROVINCES)
    for row_start in range(0, len(provinces_sorted), cols_per_row):
        row = provinces_sorted[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for i, prov in enumerate(row):
            mode = PROVINCE_MODES.get(prov, "")
            with cols[i]:
                if st.button(
                    f"{prov}\n{mode}",
                    key=f"prov_{prov}",
                    use_container_width=True,
                ):
                    state.set_province(prov)
                    st.session_state["onboarding"] = state
                    st.rerun()


def _render_step_score(state: OnboardingState) -> None:
    """Step 2: Score input."""
    import streamlit as st

    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        f"<h3 style='margin-bottom:0.2rem;'>📊 第 2 步 / 共 3 步</h3>"
        f"<p style='color:#666;font-size:0.9rem;'>已选省份: <b>{state.province}</b></p>"
        "<p style='color:#666;font-size:0.9rem;'>输入你的高考成绩（或预估分）</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    score = st.number_input(
        "高考分数",
        min_value=0,
        max_value=900,
        value=state.score if state.score is not None else 500,
        step=10,
        key="onboarding_score_input",
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅ 上一步", key="score_prev", use_container_width=True):
            state.step = 1
            st.session_state["onboarding"] = state
            st.rerun()
    with col2:
        if st.button("下一步 ➡", key="score_next", use_container_width=True):
            state.set_score(int(score))
            st.session_state["onboarding"] = state
            st.rerun()


def _render_step_subject_interest(state: OnboardingState) -> None:
    """Step 3: Subject type + interest selection."""
    import streamlit as st

    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        f"<h3 style='margin-bottom:0.2rem;'>📚 第 3 步 / 共 3 步</h3>"
        f"<p style='color:#666;font-size:0.9rem;'>"
        f"{state.province} · {state.score}分</p>"
        "<p style='color:#666;font-size:0.9rem;'>选择选科组合和兴趣方向</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    subject = st.radio(
        "选科组合",
        SUBJECT_TYPES,
        index=0,
        horizontal=False,
        key="onboarding_subject_radio",
    )

    interest = st.selectbox(
        "专业兴趣方向（可稍后调整）",
        INTERESTS,
        index=0,
        key="onboarding_interest_select",
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅ 上一步", key="subj_prev", use_container_width=True):
            state.step = 2
            st.session_state["onboarding"] = state
            st.rerun()
    with col2:
        if st.button("🚀 开始咨询", key="subj_start", use_container_width=True):
            state.set_subject(subject)
            state.set_interest(interest)
            st.session_state["onboarding"] = state
            st.rerun()
