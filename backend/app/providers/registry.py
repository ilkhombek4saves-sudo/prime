from __future__ import annotations

from typing import Any

from app.persistence.models import ProviderType
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import ServiceProvider
from app.providers.deepseek_provider import DeepSeekProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.glm_provider import GLMProvider
from app.providers.http_provider import HTTPProvider
from app.providers.kimi_provider import KimiProvider
from app.providers.mistral_provider import MistralProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.qwen_provider import QwenProvider
from app.providers.shell_provider import ShellProvider


_PROVIDER_MAP: dict[ProviderType, type[ServiceProvider]] = {
    ProviderType.GLM: GLMProvider,
    ProviderType.OpenAI: OpenAIProvider,
    ProviderType.Anthropic: AnthropicProvider,
    ProviderType.DeepSeek: DeepSeekProvider,
    ProviderType.Mistral: MistralProvider,
    ProviderType.Gemini: GeminiProvider,
    ProviderType.Kimi: KimiProvider,
    ProviderType.Qwen: QwenProvider,
    ProviderType.Ollama: OllamaProvider,
    ProviderType.HTTP: HTTPProvider,
    ProviderType.Shell: ShellProvider,
}


def build_provider(provider_type: ProviderType, name: str, config: dict[str, Any]) -> ServiceProvider:
    provider_cls = _PROVIDER_MAP[provider_type]
    provider = provider_cls(name=name, config=config)
    provider.validate_config()
    return provider


def list_supported_provider_types() -> list[str]:
    return [item.value for item in ProviderType]
