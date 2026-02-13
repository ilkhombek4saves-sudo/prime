from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class GLMProvider(OpenAICompatibleProvider):
    provider_type = "GLM"
    _default_base_url = "https://api.z.ai/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("GLM api_key is required")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        model_cfg = (self.config.get("models") or {}).get(
            self.config.get("default_model", "glm-4.7"),
            {"cost_per_1m_input": 0.6, "cost_per_1m_output": 2.2},
        )
        return (input_tokens / 1_000_000 * float(model_cfg.get("cost_per_1m_input", 0.6))) + (
            output_tokens / 1_000_000 * float(model_cfg.get("cost_per_1m_output", 2.2))
        )
