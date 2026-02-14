"""Pydantic schemas for skill definitions."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class ToolParameter(BaseModel):
    type: str
    description: str = ""
    enum: list[str] | None = None


class ToolParameters(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = {}
    required: list[str] = []


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: ToolParameters = ToolParameters()
    handler_file: str | None = None
    handler_inline: str | None = None


class SkillDefinition(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    tools: list[ToolDefinition] = []
    hot_reload: bool = False
    path: str | None = None  # filesystem path to the skill directory
