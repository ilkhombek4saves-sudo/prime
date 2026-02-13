from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class ProviderError(RuntimeError):
    """Domain-level provider exception."""


class ServiceProvider(ABC):
    """Common provider contract for all provider implementations."""

    provider_type: str = "base"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config

    @abstractmethod
    def validate_config(self) -> None:
        """Validate provider-specific config and raise ProviderError on failure."""

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate request cost in USD."""

    def handle_error(self, error: Exception) -> ProviderError:
        message = str(error)
        if "429" in message:
            return ProviderError("Rate limit reached. Retry later.")
        if "503" in message:
            return ProviderError("Provider temporarily unavailable (503).")
        return ProviderError(message)

    @retry(
        retry=retry_if_exception_type(ProviderError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _with_retry(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # pragma: no cover
            mapped = self.handle_error(exc)
            if any(code in str(mapped) for code in ["429", "503", "Rate limit", "unavailable"]):
                raise mapped
            raise

    def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "capability": "chat", "content": prompt, "meta": kwargs}

    def generate_code(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "capability": "generate_code", "content": prompt, "meta": kwargs}

    def run_cli(self, command: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "capability": "run_cli", "command": command, "meta": kwargs}

    def run_api_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "capability": "run_api_call", "request": request}

    def generate_ui(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "capability": "generate_ui", "content": prompt, "meta": kwargs}

    def generate_slides(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "provider": self.name,
            "capability": "generate_slides",
            "content": prompt,
            "format": kwargs.get("format", "pptx"),
            "aspect_ratio": "16:9",
        }

    def transcribe_audio(self, audio_ref: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "provider": self.name,
            "capability": "transcribe_audio",
            "audio_ref": audio_ref,
            "meta": kwargs,
        }

    def generate_image(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "capability": "generate_image", "content": prompt, "meta": kwargs}
