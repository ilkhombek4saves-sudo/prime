"""
SkillLoader — load skill definitions from YAML manifests.

Each skill lives in a directory with a skill.yaml manifest.
Optionally watches for file changes and hot-reloads (requires watchdog).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from app.skills.schema import SkillDefinition, ToolDefinition, ToolParameters

logger = logging.getLogger(__name__)


class SkillLoader:
    """Load SkillDefinition objects from filesystem YAML manifests."""

    @staticmethod
    def load_skill_from_dir(dir_path: Path) -> SkillDefinition:
        """Parse skill.yaml in dir_path and return a SkillDefinition."""
        manifest_path = dir_path / "skill.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No skill.yaml in {dir_path}")

        with manifest_path.open() as f:
            data = yaml.safe_load(f)

        tools = []
        for t in data.get("tools", []):
            raw_params = t.get("parameters", {})
            params = ToolParameters(
                type=raw_params.get("type", "object"),
                properties=raw_params.get("properties", {}),
                required=raw_params.get("required", []),
            )
            tools.append(
                ToolDefinition(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=params,
                    handler_file=t.get("handler"),
                )
            )

        return SkillDefinition(
            name=data["name"],
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            tools=tools,
            hot_reload=data.get("hot_reload", False),
            path=str(dir_path),
        )

    @staticmethod
    def execute_skill_handler(
        skill: SkillDefinition,
        tool_name: str,
        args: dict,
    ) -> str:
        """Execute a skill tool by loading and calling its handler module."""
        if not skill.path:
            return f"Error: skill {skill.name} has no path"

        tool = next((t for t in skill.tools if t.name == tool_name), None)
        if not tool:
            return f"Error: tool {tool_name} not found in skill {skill.name}"

        handler_file = tool.handler_file or "handler.py"
        handler_path = Path(skill.path) / handler_file

        if not handler_path.exists():
            return f"Error: handler file not found: {handler_path}"

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"skill_{skill.name}_{tool_name}", handler_path
        )
        if spec is None or spec.loader is None:
            return f"Error: cannot load handler from {handler_path}"

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            return f"Error loading handler: {exc}"

        handler_fn = getattr(module, f"handle_{tool_name}", None)
        if not handler_fn:
            # Fall back to generic 'handle' function
            handler_fn = getattr(module, "handle", None)
        if not handler_fn:
            return f"Error: no handle_{tool_name}() in {handler_path}"

        try:
            return str(handler_fn(**args))
        except Exception as exc:
            return f"Handler error: {exc}"


class SkillWatcher:
    """Watch workspace/skills/ directories for changes and hot-reload."""

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = workspace_path
        self._observer: Any = None

    def start(self) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def on_modified(self, event):
                    if event.src_path.endswith("skill.yaml"):
                        skill_dir = Path(event.src_path).parent
                        from app.skills.registry import SkillsRegistry
                        SkillsRegistry.hot_reload_skill(str(skill_dir))

            self._observer = Observer()
            skills_dir = str(Path(self.workspace_path) / "skills")
            self._observer.schedule(_Handler(), skills_dir, recursive=True)
            self._observer.start()
            logger.info("SkillWatcher started for: %s", skills_dir)
        except ImportError:
            logger.debug("watchdog not installed — hot-reload disabled")
        except Exception as exc:
            logger.warning("SkillWatcher start error: %s", exc)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
