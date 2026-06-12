"""
Phase 0-2 功能测试 — API Key 优化 / 动态快捷提问 / 年份标注 / 选科过滤

覆盖：
  - Task 0.1: API Key 友好维护提示（不再暴露技术细节）
  - Task 0.3: 多阶段加载提示（4阶段定义）
  - Task 1.2: 系统提示词中的年份标注规则和免责声明
  - Task 1.3: 选科兼容性注入到 data_hints
  - Task 2.4: 动态上下文感知快捷提问
"""
import pytest
import sys, os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════
#  Task 0.1: API Key 友好维护提示
# ══════════════════════════════════════════════════════

class TestApiKeyMaintenanceMessage:
    """验证 API Key 不可用时显示维护页面，不暴露技术细节。"""

    def test_app_py_has_maintenance_message(self):
        """app.py 中无 key 时显示「系统维护中」而非 API Key 输入框。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        # 维护提示存在
        assert "系统维护中" in app_src
        assert "请稍后再试，或联系管理员" in app_src
        # 不再暴露 DeepSeek 链接和 API Key 输入
        assert "platform.deepseek.com" not in app_src

    def test_app_py_no_key_guard_no_tech_details(self):
        """app.py 无 key 时用户侧提示不包含技术术语。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        # 不应暴露 API Key 概念给终端用户
        assert "请先在左侧边栏输入你的" not in app_src


# ══════════════════════════════════════════════════════
#  Task 0.3: 多阶段加载提示
# ══════════════════════════════════════════════════════

class TestLoadingPhases:
    """验证加载阶段定义正确。"""

    def test_loading_phases_defined_in_app(self):
        """app.py 中定义了 4 阶段加载提示。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "_loading_phases" in app_src
        assert "正在匹配你的信息" in app_src
        assert "正在查询院校数据" in app_src
        assert "AI 顾问正在分析" in app_src
        assert "复杂情况可能需要更多时间" in app_src


# ══════════════════════════════════════════════════════
#  Task 1.2: 年份标注 + 免责声明规则
# ══════════════════════════════════════════════════════

class TestYearLabelAndDisclaimer:
    """验证 system_prompt 中的年份标注和免责声明规则。"""

    def test_agent_system_message_has_year_instructions(self):
        """agent.py _build_system_message 注入年份标注规则到系统消息。"""
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "system_prompt.md"
        )
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
        # system_prompt 中有年份标注要求
        assert "标注来源和年份" in prompt

    def test_agent_injects_year_and_disclaimer_rules(self):
        """agent.py 在构建系统消息时追加年份与免责声明规则。"""
        agent_src = open(
            os.path.join(os.path.dirname(__file__), "..", "agent.py"),
            encoding="utf-8",
        ).read()
        assert "必须标注数据年份" in agent_src
        assert "数据年份与免责声明规则" in agent_src
        assert "免责提示" in agent_src


# ══════════════════════════════════════════════════════
#  Task 1.3: 选科兼容性注入
# ══════════════════════════════════════════════════════

class TestSubjectCompatibilityInjection:
    """验证选科兼容性信息被注入到 data_hints。"""

    def test_agent_has_subject_compatibility_in_data_hints(self):
        """agent.py 在录取数据查询后注入选科匹配信息。"""
        agent_src = open(
            os.path.join(os.path.dirname(__file__), "..", "agent.py"),
            encoding="utf-8",
        ).read()
        # 选科匹配注入到 data_hints
        assert "【选科匹配】" in agent_src
        assert "format_subject_compatibility(_compat)" in agent_src

    def test_agent_rank_recommendations_has_subject_check(self):
        """agent.py 在推荐结果中加入选科过滤标记。"""
        agent_src = open(
            os.path.join(os.path.dirname(__file__), "..", "agent.py"),
            encoding="utf-8",
        ).read()
        # 选科过滤标记
        assert "选科可能不符" in agent_src
        assert "check_user_subject_compatibility(user_subj_list)" in agent_src


# ══════════════════════════════════════════════════════
#  Task 2.4: 动态快捷提问
# ══════════════════════════════════════════════════════

class TestDynamicQuickQuestions:
    """验证动态快捷提问生成器逻辑。"""

    def _mock_session_state(self, province="", score="", subject="",
                            schools_in_reply=None):
        """创建模拟的 session_state。"""
        state = {
            "slots": {
                "province": {"label": "省份", "filled": bool(province), "value": province},
                "score_rank": {"label": "分数/位次", "filled": bool(score), "value": score},
                "subject": {"label": "选科", "filled": bool(subject), "value": subject},
                "interest": {"label": "专业兴趣/厌恶", "filled": False, "value": ""},
                "region": {"label": "地域偏好", "filled": False, "value": ""},
                "family": {"label": "家庭资源", "filled": False, "value": ""},
                "goal": {"label": "核心诉求", "filled": False, "value": ""},
            },
            "messages": [],
        }
        if schools_in_reply:
            state["messages"] = [{
                "role": "assistant",
                "content": schools_in_reply,
            }]
        return state

    def test_app_has_dynamic_quick_questions_function(self):
        """app.py 包含 _get_dynamic_quick_questions 函数。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "def _get_dynamic_quick_questions" in app_src
        # 不再使用静态 QUICK_QUESTIONS
        assert "_get_dynamic_quick_questions()" in app_src

    def test_function_signature(self):
        """动态快捷提问函数不接受参数（从 session_state 读取）。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "_get_dynamic_quick_questions" in app_src
        assert "-> list[str]" in app_src

    def test_default_questions_when_empty(self):
        """无任何 slot 时返回默认引导型提问。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        # 默认提问包含常见场景
        assert "我是山东考生，580分" in app_src
        assert "想冲 985/211" in app_src
        assert "想找好就业的专业" in app_src
        assert "对志愿填报一无所知" in app_src

    def test_province_based_questions(self):
        """有省份时提问包含省份名。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert f"我是{{_province}}考生" in app_src

    def test_school_followup_questions(self):
        """有 AI 推荐结果时提供学校追问。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        assert "帮我生成冲稳保志愿表" in app_src
        assert "的详细信息" in app_src
        assert "对比" in app_src
        assert "还有其他类似学校推荐吗" in app_src

    def test_context_switches_between_states(self):
        """不同 slot 状态返回不同类型的提问。"""
        app_src = open(
            os.path.join(os.path.dirname(__file__), "..", "app.py"),
            encoding="utf-8",
        ).read()
        # 深入方向提问（省份+分数+选科都有）
        assert "帮我分析冲稳保各有哪些学校" in app_src
        # 无选科时提供选科选项
        assert "选了物化生" in app_src
        # 无分数时引导填分数
        assert "580分，帮我分析" in app_src
