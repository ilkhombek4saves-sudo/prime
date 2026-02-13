from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from jsonschema import ValidationError, validate

from app.providers.base import ServiceProvider


class PluginExecutionError(RuntimeError):
    """Plugin-level execution exception."""


class PluginBase(ABC):
    name: str = "plugin"
    permissions: set[str] = set()
    input_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": True}

    def __init__(self, provider: ServiceProvider):
        self.provider = provider

    def validate_input(self, payload: dict[str, Any]) -> None:
        try:
            validate(payload, self.input_schema)
        except ValidationError as exc:
            raise PluginExecutionError(f"Invalid input for {self.name}: {exc.message}") from exc

    def check_permissions(self, user_role: str) -> None:
        if self.permissions and user_role not in self.permissions:
            raise PluginExecutionError(f"Role '{user_role}' cannot execute plugin '{self.name}'")

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run plugin-specific workflow and return normalized output."""
