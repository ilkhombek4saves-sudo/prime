from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class MistralProvider(OpenAICompatibleProvider):
    provider_type = "Mistral"
    _default_base_url = "https://api.mistral.ai/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("Mistral api_key is required")
