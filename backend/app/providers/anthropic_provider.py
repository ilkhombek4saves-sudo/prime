from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from app.providers.base import ProviderError
from app.providers.common import PricedProvider


class AnthropicProvider(PricedProvider):
    provider_type = "Anthropic"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("Anthropic api_key is required")

    def _stream_messages(
        self,
        *,
        client: httpx.Client,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None,
    ) -> tuple[str, dict[str, int]]:
        text_parts: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}

        stream_payload = {**payload, "stream": True}
        with client.stream("POST", url, headers=headers, json=stream_payload) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data:"):
                    continue
                data_raw = line[5:].strip()
                if not data_raw or data_raw == "[DONE]":
                    continue
                try:
                    event = json.loads(data_raw)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")
                token = ""
                if event_type == "content_block_delta":
                    token = (event.get("delta") or {}).get("text", "")
                elif event_type == "content_block_start":
                    content_block = event.get("content_block") or {}
                    if content_block.get("type") == "text":
                        token = content_block.get("text", "")

                if token:
                    text_parts.append(token)
                    if on_token:
                        try:
                            on_token(token)
                        except Exception:
                            # Callback failures should not abort provider response.
                            pass

                if event_type == "message_start":
                    message_usage = ((event.get("message") or {}).get("usage") or {})
                    usage["input_tokens"] = message_usage.get("input_tokens", usage["input_tokens"]) or 0
                elif event_type == "message_delta":
                    delta_usage = event.get("usage") or {}
                    usage["output_tokens"] = delta_usage.get("output_tokens", usage["output_tokens"]) or 0

        return "".join(text_parts), usage

    def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        api_key = self.config.get("api_key", "")
        base_url = self.config.get("api_base", "https://api.anthropic.com").rstrip("/")
        model = kwargs.get("model") or self.config.get("default_model", "claude-3-5-sonnet-20241022")
        model_cfg = (self.config.get("models") or {}).get(model, {})
        max_tokens = kwargs.get("max_tokens") or model_cfg.get("max_tokens", 2048)
        stream = bool(kwargs.get("stream", False))
        on_token: Callable[[str], None] | None = kwargs.get("on_token")

        history: list[dict] = kwargs.get("history") or []
        messages = list(history) + [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if kwargs.get("system"):
            payload["system"] = kwargs["system"]

        # Optional extended thinking (Claude 3.7+)
        if self.config.get("thinking_enabled") and kwargs.get("thinking_budget_tokens"):
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": kwargs["thinking_budget_tokens"],
            }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=120) as client:
                endpoint = f"{base_url}/v1/messages"
                if stream:
                    content, usage = self._stream_messages(
                        client=client,
                        url=endpoint,
                        headers=headers,
                        payload=payload,
                        on_token=on_token,
                    )
                    return {
                        "provider": self.name,
                        "type": self.provider_type,
                        "model": model,
                        "content": content,
                        "usage": usage,
                    }

                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Anthropic API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        # Extract text from content blocks (may include thinking blocks)
        text_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content = block["text"]
                break

        usage = data.get("usage", {})
        return {
            "provider": self.name,
            "type": self.provider_type,
            "model": model,
            "content": text_content,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        }
