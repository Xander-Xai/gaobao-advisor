"""HTTP client for communicating with gaobao-advisor API."""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────

API_BASE_URL = os.environ.get("GAOBAO_API_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("GAOBAO_API_KEY", "")
TIMEOUT = float(os.environ.get("GAOBAO_TIMEOUT", "30"))


def _get_headers() -> dict[str, str]:
    """Build request headers with optional auth."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "gaobao-mcp-client/1.0.0",
    }
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


class GaobaoClient:
    """HTTP client for gaobao-advisor API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        self.api_key = api_key or API_KEY
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(TIMEOUT),
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "gaobao-mcp-client/1.0.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request and return JSON response."""
        url = f"{self.base_url}{path}"
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("HTTP %s %s failed: %s - %s", method, url, e.response.status_code, e.response.text)
            # Try to parse error response
            try:
                err_body = e.response.json()
                detail = err_body.get("detail", err_body.get("message", str(e)))
            except json.JSONDecodeError:
                detail = e.response.text or str(e)
            raise GaobaoAPIError(
                f"API error {e.response.status_code}: {detail}",
                status_code=e.response.status_code,
            ) from e
        except httpx.ConnectError as e:
            raise GaobaoAPIError(
                f"无法连接到 gaobao-advisor API ({self.base_url})。请确认服务已启动。",
                status_code=0,
            ) from e
        except httpx.TimeoutException as e:
            raise GaobaoAPIError(
                f"请求超时（{TIMEOUT}秒）。服务可能负载过高或不可用。",
                status_code=0,
            ) from e

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET request."""
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST request."""
        return await self.request("POST", path, json_data=json_data)

    async def put(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """PUT request."""
        return await self.request("PUT", path, json_data=json_data)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class GaobaoAPIError(Exception):
    """Custom exception for gaobao-advisor API errors."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


# ── Singleton client instance ───────────────────────────────

_client: GaobaoClient | None = None


def get_client() -> GaobaoClient:
    """Get or create the singleton client instance."""
    global _client
    if _client is None:
        _client = GaobaoClient()
    return _client


def reset_client() -> None:
    """Reset the singleton client (for testing)."""
    global _client
    _client = None
