"""Skill registry — load and manage agent skills/plugins"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prime.config.settings import SKILLS_DIR


class SkillRegistry:
    """Manages loadable skills from ~/.prime/skills/ directory."""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, dict] = {}
        self._load_builtins()
        self._load_user_skills()

    def _load_builtins(self):
        """Register built-in skills."""
        self._skills["status"] = {
            "name": "status",
            "description": "Show system status",
            "type": "builtin",
            "handler": self._skill_status,
        }
        self._skills["notify_telegram"] = {
            "name": "notify_telegram",
            "description": "Send a Telegram notification",
            "type": "builtin",
            "handler": self._skill_notify,
        }

    def _load_user_skills(self):
        """Load user-defined skills from ~/.prime/skills/*.json"""
        for f in self.skills_dir.glob("*.json"):
            try:
                skill = json.loads(f.read_text())
                name = skill.get("name", f.stem)
                self._skills[name] = skill
            except Exception as e:
                print(f"  ! Failed to load skill {f.name}: {e}")

    def list_skills(self) -> list[dict]:
        return [{"name": k, "description": v.get("description", ""), "type": v.get("type", "user")}
                for k, v in self._skills.items()]

    def get_skill(self, name: str) -> dict | None:
        return self._skills.get(name)

    def run_skill(self, name: str, args: dict = None) -> str:
        skill = self._skills.get(name)
        if not skill:
            return f"Skill not found: {name}"
        handler = skill.get("handler")
        if callable(handler):
            return handler(args or {})
        command = skill.get("command", "")
        if command:
            import subprocess
            for k, v in (args or {}).items():
                command = command.replace(f"{{{k}}}", str(v))
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return (result.stdout + result.stderr).strip()
        return f"Skill '{name}' has no handler or command."

    def install_skill(self, skill_def: dict) -> str:
        name = skill_def.get("name")
        if not name:
            return "Error: skill must have a name"
        skill_file = self.skills_dir / f"{name}.json"
        skill_file.write_text(json.dumps(skill_def, indent=2))
        self._skills[name] = skill_def
        return f"OK: Installed skill '{name}'"

    def uninstall_skill(self, name: str) -> str:
        skill_file = self.skills_dir / f"{name}.json"
        if skill_file.exists():
            skill_file.unlink()
        self._skills.pop(name, None)
        return f"OK: Uninstalled skill '{name}'"

    # ── Built-in handlers ──────────────────────────────────────────────────
    def _skill_status(self, args: dict) -> str:
        from prime.core.agent import get_system_info
        from prime.config.settings import settings
        info = get_system_info()
        return (f"Prime Status\n"
                f"Host: {info['hostname']}\n"
                f"OS: {info['os']}\n"
                f"Provider: {settings.best_provider()}\n"
                f"APIs: {', '.join(settings.available_providers())}")

    def _skill_notify(self, args: dict) -> str:
        from prime.integrations.telegram import notify
        message = args.get("message", "Hello from Prime!")
        success = notify(message)
        return "OK: Notification sent" if success else "Error: Failed to send notification"


# Singleton
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
