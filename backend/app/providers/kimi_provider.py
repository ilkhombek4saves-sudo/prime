from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class KimiProvider(OpenAICompatibleProvider):
    provider_type = "Kimi"
    _default_base_url = "https://api.moonshot.cn/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("Kimi api_key is required")
