"""
Content-Security-Policy Middleware with Nonce Support.

Generates a unique nonce for each request and injects it into:
1. CSP header (script-src 'nonce-xxx')
2. HTML response (via meta tag or inline script attribute)

This eliminates the need for 'unsafe-inline' in script-src, improving security.

Usage:
    from server.middleware.csp import CSPMiddleware

    app.add_middleware(CSPMiddleware)
"""

from __future__ import annotations

import base64
import os
import re
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CSPMiddleware(BaseHTTPMiddleware):
    """Middleware to add CSP header with per-request nonce."""

    def __init__(
        self,
        app,
        policy: str | None = None,
        nonce_length: int = 16,
    ):
        """Initialize CSP middleware.

        Args:
            app: ASGI application
            policy: CSP policy template (use {nonce} placeholder)
            nonce_length: Length of nonce in bytes (default 16)
        """
        super().__init__(app)
        self.nonce_length = nonce_length

        # Default policy with nonce placeholder
        self.policy_template = policy or (
            "default-src 'self'; "
            "script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'nonce-{nonce}'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self';"
        )

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce."""
        return base64.b64encode(os.urandom(self.nonce_length)).decode("ascii")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add CSP header with nonce."""
        # Generate nonce for this request
        nonce = self._generate_nonce()

        # Call next middleware/handler
        response = await call_next(request)

        # Only modify HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        # Guard: response may be a streaming response without a .body attribute
        if not hasattr(response, "body"):
            return response

        # Build CSP header with nonce
        csp_header = self.policy_template.format(nonce=nonce)

        # Add CSP header
        response.headers["Content-Security-Policy"] = csp_header

        # Inject nonce into HTML (for inline scripts/styles)
        body = response.body.decode("utf-8")

        # Add nonce to <script> tags without src
        body = re.sub(
            r'<script([^>]*)>',
            lambda m: f'<script{m.group(1)} nonce="{nonce}">' if 'src=' not in m.group(1) else f'<script{m.group(1)}>',
            body
        )

        # Add nonce to <style> tags
        body = re.sub(
            r'<style([^>]*)>',
            f'<style\\1 nonce="{nonce}">',
            body
        )

        # Update response body
        response.body = body.encode("utf-8")
        response.headers["content-length"] = str(len(response.body))

        return response


# ── Helper Functions ────────────────────────────────────────


def get_csp_nonce_from_request(request: Request) -> str | None:
    """Extract nonce from request state (set by middleware)."""
    return getattr(request.state, "csp_nonce", None)
