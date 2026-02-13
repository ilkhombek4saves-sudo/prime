from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.providers.base import ProviderError, ServiceProvider


class HTTPProvider(ServiceProvider):
    provider_type = "HTTP"
    _ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

    def validate_config(self) -> None:
        base_url = str(self.config.get("base_url", "")).strip()
        if not base_url:
            raise ProviderError("HTTP provider requires base_url")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProviderError("HTTP provider base_url must be a valid http(s) URL")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def _resolve_url(self, request_url: str) -> str:
        parsed = urlparse(request_url)
        if parsed.scheme and parsed.netloc:
            if not self.config.get("allow_absolute_url", False):
                raise ProviderError("Absolute URLs are disabled for this HTTP provider")
            return request_url
        base_url = str(self.config.get("base_url", "")).rstrip("/") + "/"
        return urljoin(base_url, request_url.lstrip("/"))

    def run_api_call(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "GET").upper()
        if method not in self._ALLOWED_METHODS:
            raise ProviderError(f"Method '{method}' is not allowed")

        request_url = str(request.get("url", "")).strip()
        if not request_url:
            raise ProviderError("HTTPProvider request url is required")
        url = self._resolve_url(request_url)

        headers = {
            **(self.config.get("default_headers") or {}),
            **(request.get("headers") or {}),
        }
        body = request.get("body")
        timeout = float(self.config.get("request_timeout_seconds", 30))

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(method=method, url=url, headers=headers, json=body)
        except httpx.RequestError as exc:
            raise ProviderError(f"HTTP request failed: {exc}") from exc

        try:
            payload: Any = response.json()
        except Exception:
            payload = {"text": response.text}

        if response.status_code >= 400:
            raise self.handle_error(
                RuntimeError(
                    f"HTTP {response.status_code} for {method} {url}: {payload}"
                )
            )
        return {
            "provider": self.name,
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "payload": payload,
        }
