from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


# ---------------------------------------------------------------------------
# Pydantic schemas for each config file
# ---------------------------------------------------------------------------

class BotConfig(BaseModel):
    name: str
    # Either a literal token or an env-var reference (token_env: MY_VAR_NAME)
    token: str | None = None
    token_env: str | None = None
    channels: list[str] = Field(default_factory=list)
    allowed_user_ids: list[int] = Field(default_factory=list)
    active: bool = True
    provider_defaults: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @field_validator("token_env", mode="after")
    @classmethod
    def token_or_token_env_required(cls, v: str | None, info: Any) -> str | None:
        if v is None and not info.data.get("token"):
            raise ValueError("Bot must have either 'token' or 'token_env'")
        return v


class BotsFile(BaseModel):
    version: int = 1
    bots: list[BotConfig] = Field(default_factory=list)


class ModelConfig(BaseModel):
    max_tokens: int = 2048
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    model_config = {"extra": "allow"}


class ProviderConfig(BaseModel):
    name: str
    type: str
    api_key: str | None = None
    api_base: str | None = None
    default_model: str | None = None
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    thinking_enabled: bool = False
    active: bool = True
    rate_limits: dict[str, Any] = Field(default_factory=dict)
    allowed_scripts: list[str] | None = None

    model_config = {"extra": "allow"}

    KNOWN_TYPES: ClassVar[frozenset[str]] = frozenset({
        "OpenAI", "Anthropic", "GLM", "DeepSeek", "Mistral",
        "Gemini", "Kimi", "Qwen", "Ollama", "HTTP", "Shell",
    })

    @field_validator("type")
    @classmethod
    def type_must_be_known(cls, v: str) -> str:
        if v not in cls.KNOWN_TYPES:
            raise ValueError(
                f"Unknown provider type '{v}'. Allowed: {sorted(cls.KNOWN_TYPES)}"
            )
        return v


class ProvidersFile(BaseModel):
    version: int = 1
    providers: list[ProviderConfig] = Field(default_factory=list)


class PluginConfig(BaseModel):
    name: str
    provider: str | None = None
    permissions: list[str] = Field(default_factory=list)
    active: bool = True

    model_config = {"extra": "allow"}


class PluginsFile(BaseModel):
    version: int = 1
    plugins: list[PluginConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ConfigValidationError(RuntimeError):
    """Raised when any config file fails strict schema validation."""


class ConfigLoader:
    def __init__(self, base_path: str = "config") -> None:
        self.base_path = Path(base_path)

    def _expand_env_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._expand_env_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand_env_value(v) for v in value]
        if isinstance(value, str):
            return self._expand_env_string(value)
        return value

    def _expand_env_string(self, value: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            default = match.group(2)
            env_value = os.getenv(key)
            if env_value is not None:
                return env_value
            if default is not None:
                return default
            logger.warning("Config placeholder %s is not set; substituting empty string", key)
            return ""

        return _ENV_VAR_PATTERN.sub(_replace, value)

    def load_yaml(self, file_name: str) -> dict[str, Any]:
        path = self.base_path / file_name
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        return self._expand_env_value(data)

    def load_all(self) -> dict[str, dict[str, Any]]:
        return {
            "bots": self.load_yaml("bots.yaml"),
            "providers": self.load_yaml("providers.yaml"),
            "plugins": self.load_yaml("plugins.yaml"),
        }

    def load_and_validate(self) -> dict[str, Any]:
        """Load + validate all config files. Raises ConfigValidationError on any schema mismatch.

        Call at boot to fail fast rather than discovering bad config at runtime.
        """
        raw = self.load_all()
        errors: list[str] = []
        validated: dict[str, Any] = {}

        for key, model_cls in [
            ("bots", BotsFile),
            ("providers", ProvidersFile),
            ("plugins", PluginsFile),
        ]:
            try:
                validated[key] = model_cls.model_validate(raw.get(key, {})).model_dump()
            except ValidationError as exc:
                errors.append(f"{key}.yaml: {exc}")

        if errors:
            detail = "\n".join(errors)
            raise ConfigValidationError(
                f"Config validation failed — fix the following before starting:\n{detail}"
            )

        logger.info(
            "Config validated OK: %d bots, %d providers, %d plugins",
            len(validated["bots"].get("bots", [])),
            len(validated["providers"].get("providers", [])),
            len(validated["plugins"].get("plugins", [])),
        )
        return validated
