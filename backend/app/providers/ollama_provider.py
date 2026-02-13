from typing import Any

from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama exposes an OpenAI-compatible /v1 endpoint.

    Config accepts either:
      - base_url: full URL including port (default http://localhost:11434/v1)
      - docker_host: legacy alias for base_url
    No api_key required for local Ollama.
    """

    provider_type = "Ollama"
    _default_base_url = "http://localhost:11434/v1"

    def validate_config(self) -> None:
        if not self.config.get("models"):
            raise ProviderError(f"{self.name}: models config is required")
        # Ollama does not require an api_key

    def _api_key(self) -> str:
        # Ollama accepts any non-empty string as the bearer key
        return self.config.get("api_key", "ollama")

    def _base_url(self) -> str:
        return (
            self.config.get("base_url")
            or self.config.get("docker_host")
            or self._default_base_url
        ).rstrip("/")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Ollama is local — no cost
