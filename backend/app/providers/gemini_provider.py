from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import ProviderError
from app.providers.common import PricedProvider

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(PricedProvider):
    provider_type = "Gemini"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("Gemini api_key is required")

    def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        api_key = self.config.get("api_key", "")
        model = kwargs.get("model") or self.config.get("default_model", "gemini-1.5-flash")
        model_cfg = (self.config.get("models") or {}).get(model, {})
        max_tokens = kwargs.get("max_tokens") or model_cfg.get("max_tokens", 2048)

        # Convert OpenAI-style history to Gemini format (role: user/model)
        history: list[dict] = kwargs.get("history") or []
        contents = []
        for msg in history:
            gemini_role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        generation_config: dict[str, Any] = {"maxOutputTokens": max_tokens}
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        # Gemini system instruction (separate field)
        if kwargs.get("system"):
            payload["systemInstruction"] = {"parts": [{"text": kwargs["system"]}]}

        url = f"{_GEMINI_BASE}/models/{model}:generateContent?key={api_key}"

        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Gemini API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc

        content = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        usage = data.get("usageMetadata", {})
        return {
            "provider": self.name,
            "type": self.provider_type,
            "model": model,
            "content": content,
            "usage": {
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
            },
        }

    def generate_image(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "provider": self.name,
            "type": self.provider_type,
            "capability": "generate_image",
            "prompt": prompt,
            "image_response_format": kwargs.get("image_response_format", "url"),
        }
