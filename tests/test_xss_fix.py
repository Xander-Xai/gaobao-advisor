"""验证 slot value 转义逻辑。"""

import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def render_slot_dot(label: str, value: str, filled: bool) -> str:
    """复刻 app.py 中 slot 渲染逻辑。"""
    cls = "slot-filled" if filled else "slot-empty"
    safe_label = html.escape(label)
    safe_value = html.escape(value if filled else "未填")
    return f'<span class="slot-dot {cls}" title="{safe_label}: {safe_value}"></span>'


def test_slot_value_escapes_script_tag():
    """slot value 中的 <script> 应被转义为文本。"""
    malicious = '<script>alert("xss")</script>'
    out = render_slot_dot("省份", malicious, True)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_slot_value_escapes_quotes():
    """属性值中的引号应被转义，防止属性注入。"""
    malicious = 'foo" onerror="alert(1)'
    out = render_slot_dot("test", malicious, True)
    assert 'onerror="alert(1)' not in out
    assert "&quot;" in out


def test_slot_value_normal_text_unchanged():
    """正常文本不应被破坏。"""
    out = render_slot_dot("省份", "湖北", True)
    assert "湖北" in out
    assert "slot-filled" in out
