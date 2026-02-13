from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    provider_type = "DeepSeek"
    _default_base_url = "https://api.deepseek.com/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("DeepSeek api_key is required")
