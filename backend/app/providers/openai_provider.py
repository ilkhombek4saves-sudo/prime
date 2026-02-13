from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    provider_type = "OpenAI"
    _default_base_url = "https://api.openai.com/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("OpenAI api_key is required")
