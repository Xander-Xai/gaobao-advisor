"""Privacy redaction helpers used by audit records and demo payloads."""

from __future__ import annotations

from server.admin.privacy import (
    mask_email,
    mask_id_card,
    mask_name,
    mask_phone,
    redact_sensitive_text,
    sanitize_detail,
)


class TestMasking:
    def test_mask_name(self):
        assert mask_name("张三") == "张*"
        assert mask_name("欧阳娜娜") == "欧**娜"
        assert mask_name("李") == "*"
        assert mask_name("") == ""

    def test_mask_phone_and_id_card(self):
        assert mask_phone("联系电话 13812345678") == "联系电话 138****5678"
        assert mask_id_card("110101199001011234") == "110101********1234"

    def test_mask_email(self):
        assert mask_email("student@example.com") == "s***@example.com"

    def test_redact_tokens_and_keys(self):
        text = "Authorization: Bearer abcdefghijklmnop sk-1234567890"
        redacted = redact_sensitive_text(text)
        assert "abcdefghijklmnop" not in redacted
        assert "sk-1234567890" not in redacted
        assert "Bearer ***" in redacted

    def test_sanitize_detail_recursively(self):
        detail = {
            "filters": {"province": "示例省·甲"},
            "password": "should-not-survive",
            "nested": [{"student_name": "张三", "phone": "13812345678"}],
            "note": "联系 13900001111 或 student@example.com",
            "count": 3,
        }
        safe = sanitize_detail(detail)
        assert safe["password"] == "***"
        assert safe["nested"][0]["student_name"] == "张*"
        assert safe["nested"][0]["phone"] == "***"
        assert "13900001111" not in safe["note"]
        assert "student@example.com" not in safe["note"]
        assert safe["count"] == 3
