"""共享工具函数（消除跨模块重复代码）。"""
import ipaddress
import re
import socket
import urllib.parse


def safe_int(value, default=None):
    """安全转 int，处理 None / 空串 / 占位符。

    >>> safe_int(42)
    42
    >>> safe_int("123")
    123
    >>> safe_int(None) is None
    True
    >>> safe_int("-", default=0)
    0
    """
    if value in (None, "", "-", "暂无"):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ── SSRF 防御 ────────────────────────────────────────

_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254",
    "metadata.google.internal", "100.100.100.200",
}


def is_safe_url(url: str) -> bool:
    """检查URL是否安全（防SSRF）：拒绝内网地址和非HTTP协议。

    增强：DNS 解析后再检查 IP（防 DNS 重绑定攻击）。
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if hostname in _BLOCKED_HOSTS:
            return False
        # 拒绝内网 IP 段（直接 IP 情况）
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass
        # 拒绝常见内网域名后缀
        for suffix in (".local", ".internal", ".localhost", ".lan"):
            if hostname.endswith(suffix):
                return False
        # DNS 解析后再检查（防 DNS 重绑定）
        try:
            resolved_ip = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(resolved_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except (socket.gaierror, ValueError):
            pass
        return True
    except Exception:
        return False


# ── HTML 清理（XSS 防御）────────────────────────────────

def sanitize_html(text: str) -> str:
    """强化HTML清理，防止XSS残留。"""
    if not text:
        return ""
    # 移除所有 script/style 标签及内容
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 移除 on* 事件属性（onclick, onerror, onload 等）
    text = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bon\w+\s*=\s*\S+', '', text, flags=re.IGNORECASE)
    # 移除 javascript: 协议
    text = re.sub(r'javascript\s*:', '', text, flags=re.IGNORECASE)
    # 移除危险标签
    text = re.sub(
        r'<\s*/?\s*(?:img|svg|iframe|object|embed|form|input|meta|link|base|applet)\b[^>]*>',
        '', text, flags=re.IGNORECASE,
    )
    # 移除所有剩余 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 清理空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text
