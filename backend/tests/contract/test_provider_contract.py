import pytest

from app.persistence.models import ProviderType
from app.providers.registry import build_provider


@pytest.mark.parametrize("provider_type", list(ProviderType))
def test_provider_contract(provider_type):
    base_cfg = {"models": {"default": {"max_tokens": 1000}}, "default_model": "default"}
    if provider_type.value in {"OpenAI", "Anthropic", "DeepSeek", "Mistral", "Gemini", "Kimi", "Qwen", "GLM"}:
        base_cfg["api_key"] = "x"
    if provider_type.value == "Ollama":
        base_cfg["docker_host"] = "http://localhost:11434"
    if provider_type.value == "HTTP":
        base_cfg["base_url"] = "https://example.com"
    if provider_type.value == "Shell":
        base_cfg["allowed_scripts"] = ["test.sh"]

    provider = build_provider(provider_type=provider_type, name="p", config=base_cfg)
    assert hasattr(provider, "validate_config")
    assert hasattr(provider, "estimate_cost")
    assert hasattr(provider, "handle_error")
