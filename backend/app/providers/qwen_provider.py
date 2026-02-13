from app.providers.base import ProviderError
from app.providers.common import OpenAICompatibleProvider


class QwenProvider(OpenAICompatibleProvider):
    provider_type = "Qwen"
    _default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def validate_config(self) -> None:
        super().validate_config()
        if not self.config.get("api_key"):
            raise ProviderError("Qwen api_key is required")
