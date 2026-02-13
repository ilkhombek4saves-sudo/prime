from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from app.providers.base import ProviderError, ServiceProvider


class PricedProvider(ServiceProvider):
    def validate_config(self) -> None:
        if not self.config.get("models"):
            raise ProviderError(f"{self.name}: models config is required")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        model = self.config.get("default_model")
        model_cfg = (self.config.get("models") or {}).get(model, {})
        input_price_1m = float(
            model_cfg.get("cost_per_1m_input", model_cfg.get("cost_per_1k_input", 0) * 1000)
        )
        output_price_1m = float(
            model_cfg.get("cost_per_1m_output", model_cfg.get("cost_per_1k_output", 0) * 1000)
        )
        return (input_tokens / 1_000_000 * input_price_1m) + (
            output_tokens / 1_000_000 * output_price_1m
        )

    def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "provider": self.name,
            "type": self.provider_type,
            "model": kwargs.get("model", self.config.get("default_model")),
            "content": prompt,
            "thinking_enabled": bool(self.config.get("thinking_enabled", False)),
            "meta": kwargs,
        }


class OpenAICompatibleProvider(PricedProvider):
    """
    Shared implementation for any provider that exposes an OpenAI-compatible
    /v1/chat/completions endpoint (OpenAI, DeepSeek, Kimi, Qwen, GLM, Ollama, …).

    Subclasses must set:
        provider_type: str
        _default_base_url: str
        _api_key_header: str   (default: "Authorization" with "Bearer …" value)
    """

    _default_base_url: str = "https://api.openai.com/v1"
    _bearer_auth: bool = True  # False → subclass overrides _auth_headers()

    def _api_key(self) -> str:
        key = self.config.get("api_key", "")
        if not key:
            raise ProviderError(f"{self.name}: api_key is required")
        return key

    def _base_url(self) -> str:
        return self.config.get("api_base", self._default_base_url).rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key()}"}

    def _build_messages(self, prompt: str, **kwargs: Any) -> list[dict]:
        """Build messages array from prompt + optional system + optional history."""
        system = kwargs.get("system")
        history: list[dict] = kwargs.get("history") or []
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return messages

    def _stream_chat_completion(
        self,
        *,
        client: httpx.Client,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None,
    ) -> tuple[str, dict[str, int]]:
        streamed_text_parts: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}

        stream_payload = {
            **payload,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        with client.stream("POST", url, headers=headers, json=stream_payload) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data:"):
                    continue
                data_raw = line[5:].strip()
                if data_raw == "[DONE]":
                    break
                try:
                    event = json.loads(data_raw)
                except json.JSONDecodeError:
                    continue

                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                token = delta.get("content")
                if token:
                    streamed_text_parts.append(token)
                    if on_token:
                        try:
                            on_token(token)
                        except Exception:
                            # Callback failures should not abort provider response.
                            pass

                usage_event = event.get("usage")
                if isinstance(usage_event, dict):
                    usage["input_tokens"] = usage_event.get("prompt_tokens", usage["input_tokens"]) or 0
                    usage["output_tokens"] = usage_event.get("completion_tokens", usage["output_tokens"]) or 0

        return "".join(streamed_text_parts), usage

    def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        model = kwargs.get("model") or self.config.get("default_model", "gpt-4o")
        model_cfg = (self.config.get("models") or {}).get(model, {})
        max_tokens = kwargs.get("max_tokens") or model_cfg.get("max_tokens", 2048)
        stream = bool(kwargs.get("stream", False))
        on_token: Callable[[str], None] | None = kwargs.get("on_token")

        payload: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(prompt, **kwargs),
            "max_tokens": max_tokens,
        }

        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        if kwargs.get("top_p") is not None:
            payload["top_p"] = kwargs["top_p"]

        headers = {
            "Content-Type": "application/json",
            **self._auth_headers(),
        }

        try:
            with httpx.Client(timeout=120) as client:
                endpoint = f"{self._base_url()}/chat/completions"
                if stream:
                    content, usage = self._stream_chat_completion(
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
                f"{self.provider_type} API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"{self.provider_type} request failed: {exc}") from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "provider": self.name,
            "type": self.provider_type,
            "model": model,
            "content": content,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }
