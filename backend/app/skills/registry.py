"""
SkillsRegistry — central registry for all agent skills/tools.

Bundled skills are registered at startup. Workspace skills are loaded
from YAML manifests found under the agent's workspace directory.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from app.skills.schema import SkillDefinition, ToolDefinition

logger = logging.getLogger(__name__)

_registry: dict[str, SkillDefinition] = {}  # name → SkillDefinition
_handlers: dict[str, Any] = {}  # "skill.tool" → callable


class SkillsRegistry:
    """Singleton-style registry for skill tool definitions."""

    @staticmethod
    def register_bundled() -> None:
        """Load all bundled skills from app.skills.bundled.*"""
        bundled_modules = [
            "app.skills.bundled.file_ops",
            "app.skills.bundled.web_search",
            "app.skills.bundled.code_runner",
            "app.skills.bundled.shell",
        ]
        for mod_path in bundled_modules:
            try:
                mod = importlib.import_module(mod_path)
                skill: SkillDefinition = mod.SKILL
                SkillsRegistry._register(skill, mod)
                logger.debug("Bundled skill registered: %s", skill.name)
            except Exception as exc:
                logger.warning("Failed to register bundled skill %s: %s", mod_path, exc)

    @staticmethod
    def register_from_workspace(path: str) -> list[str]:
        """
        Scan a workspace directory for skill.yaml manifests and register them.
        Returns list of registered skill names.
        """
        from app.skills.loader import SkillLoader

        registered = []
        workspace = Path(path)
        skills_dir = workspace / "skills"
        if not skills_dir.exists():
            return registered

        for skill_yaml in skills_dir.glob("*/skill.yaml"):
            try:
                skill = SkillLoader.load_skill_from_dir(skill_yaml.parent)
                SkillsRegistry._register(skill, None)
                registered.append(skill.name)
                logger.info("Workspace skill registered: %s", skill.name)
            except Exception as exc:
                logger.warning("Failed to load skill from %s: %s", skill_yaml, exc)

        return registered

    @staticmethod
    def _register(skill: SkillDefinition, module: Any) -> None:
        _registry[skill.name] = skill
        if module:
            for tool in skill.tools:
                handler_name = f"handle_{tool.name}"
                handler = getattr(module, handler_name, None)
                if handler:
                    _handlers[f"{skill.name}.{tool.name}"] = handler

    @staticmethod
    def get_tools_for_agent(agent_id: str | None = None) -> list[ToolDefinition]:
        """Return all registered tool definitions (for any agent)."""
        tools = []
        for skill in _registry.values():
            tools.extend(skill.tools)
        return tools

    @staticmethod
    def get_tools_openai() -> list[dict]:
        """Return tool definitions in OpenAI format."""
        tools = []
        for tool in SkillsRegistry.get_tools_for_agent():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.model_dump(),
                },
            })
        return tools

    @staticmethod
    def get_tools_anthropic() -> list[dict]:
        """Return tool definitions in Anthropic format."""
        tools = []
        for tool in SkillsRegistry.get_tools_for_agent():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters.model_dump(),
            })
        return tools

    @staticmethod
    def execute_skill_tool(tool_name: str, args: dict) -> str | None:
        """
        Try to execute tool_name using a registered skill handler.
        Returns str result or None if not found.
        """
        # Search across all skills
        for skill_name, skill in _registry.items():
            for tool in skill.tools:
                if tool.name == tool_name:
                    handler_key = f"{skill_name}.{tool_name}"
                    handler = _handlers.get(handler_key)
                    if handler:
                        try:
                            return str(handler(**args))
                        except Exception as exc:
                            return f"Skill error ({tool_name}): {exc}"
        return None

    @staticmethod
    def list_skills() -> list[dict]:
        """Return summary of all registered skills."""
        return [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "tools": [t.name for t in s.tools],
                "path": s.path,
            }
            for s in _registry.values()
        ]

    @staticmethod
    def get_skill(name: str) -> SkillDefinition | None:
        return _registry.get(name)

    @staticmethod
    def hot_reload_skill(path: str) -> bool:
        from app.skills.loader import SkillLoader
        try:
            skill = SkillLoader.load_skill_from_dir(Path(path))
            _registry[skill.name] = skill
            logger.info("Hot-reloaded skill: %s", skill.name)
            return True
        except Exception as exc:
            logger.error("Hot-reload failed for %s: %s", path, exc)
            return False
