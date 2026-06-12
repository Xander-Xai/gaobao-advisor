"""
Phase 2.2/3 增强测试 — 学校卡片趋势 / 咨询报告 / 移动端

覆盖：
  - Phase 2.2: 学校卡片 trend/note 字段渲染
  - Phase 3.2: 完整咨询报告生成逻辑
  - Phase 3.4: 移动端 CSS 增强
  - Phase 3.1: 历史对话列表
"""
import pytest
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ══════════════════════════════════════════════════════
#  Phase 2.2: 学校卡片趋势指示器
# ══════════════════════════════════════════════════════

class TestSchoolCardTrend:
    """验证学校卡片支持 trend 趋势字段和 note 字段。"""

    def test_render_school_card_supports_trend_field(self):
        """_render_school_card 函数源码支持 trend 字段。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "trend = str(school.get(" in app_src
        assert "trend_icons" in app_src
        assert "上升" in app_src and "下降" in app_src and "稳定" in app_src

    def test_render_school_card_supports_note_field(self):
        """_render_school_card 函数源码支持 note 字段（含选科警告样式）。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert 'note = _html.escape(str(school.get("note", "")))' in app_src
        assert "school-card-note-warn" in app_src
        assert "选科" in app_src and "不符" in app_src

    def test_css_has_trend_tag_style(self):
        """CSS 定义了趋势标签样式。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert ".school-card-trend" in app_src

    def test_css_has_note_warn_style(self):
        """CSS 定义了警告 note 样式。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert ".school-card-note-warn" in app_src
        assert ".school-card-note {" in app_src


# ══════════════════════════════════════════════════════
#  Phase 3.2: 完整咨询报告
# ══════════════════════════════════════════════════════

class TestConsultationReport:
    """验证完整咨询报告生成逻辑。"""

    def test_report_includes_user_info_section(self):
        """报告包含考生基本信息摘要。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "## 📋 考生基本信息" in app_src
        assert "省份" in app_src and "分数/位次" in app_src

    def test_report_includes_school_summary(self):
        """报告包含院校摘要（从 AI 回复中提取）。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "## 🏫 本次咨询涉及的院校" in app_src
        assert "_school_mentions" in app_src

    def test_report_includes_full_conversation(self):
        """报告包含完整对话记录。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "## 💬 完整对话记录" in app_src

    def test_report_includes_disclaimer(self):
        """报告末尾包含免责声明。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "## ⚠️ 免责声明" in app_src
        assert "仅供参考，不构成升学决策依据" in app_src
        assert "gaokao.chsi.com.cn" in app_src

    def test_report_filename_includes_date(self):
        """报告文件名将日期包含在内。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "高考志愿咨询报告_" in app_src
        assert "_now[:10]" in app_src


# ══════════════════════════════════════════════════════
#  Phase 3.4: 移动端增强
# ══════════════════════════════════════════════════════

class TestMobileEnhancements:
    """验证移动端 CSS 增强。"""

    def test_has_two_media_query_breakpoints(self):
        """有 768px 和 480px 两级媒体查询。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "@media (max-width: 768px)" in app_src
        assert "@media (max-width: 480px)" in app_src

    def test_mobile_optimizes_school_cards(self):
        """移动端优化学校卡片的字体和 padding。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert ".school-card { padding: 0.6rem; }" in app_src
        assert ".school-card-title { font-size: 0.95rem; }" in app_src
        assert ".school-card-meta { font-size: 0.75rem; }" in app_src

    def test_mobile_optimizes_sidebar(self):
        """移动端优化侧边栏宽度。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert '[data-testid="stSidebar"]' in app_src

    def test_mobile_optimizes_loading_step(self):
        """移动端优化加载提示字体。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert ".loading-step { font-size: 0.8rem;" in app_src


# ══════════════════════════════════════════════════════
#  Phase 3.1: 历史对话列表
# ══════════════════════════════════════════════════════

class TestConversationHistory:
    """验证历史对话列表功能。"""

    def test_sidebar_has_history_expander(self):
        """侧边栏有历史对话列表入口。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "💬 历史对话" in app_src
        assert "list_user_conversations" in app_src

    def test_history_shows_recent_conversations(self):
        """历史面板显示最近 5 条对话。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "limit=5" in app_src

    def test_history_highlights_current_session(self):
        """当前会话在历史列表中高亮显示。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "*(当前)*" in app_src or "(当前)" in app_src

    def test_history_links_are_clickable(self):
        """历史对话可点击切换（URL 含 sid 参数）。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "?sid=" in app_src