"""
PiAgent — LLM-powered skill generator.

The Pi coding agent writes new skills (skill.yaml + handler.py) from a
natural-language description and installs them into the workspace.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_YAML_TEMPLATE = """\
name: {name}
version: "1.0"
description: "{description}"
tools:
  - name: {tool_name}
    description: "{tool_description}"
    parameters:
      type: object
      properties:
        input:
          type: string
          description: "Input for the tool"
      required: [input]
    handler: handler.py
hot_reload: true
"""

HANDLER_TEMPLATE = """\
\"\"\"
Auto-generated handler for skill: {name}
Description: {description}
\"\"\"


def handle_{tool_name}(input: str) -> str:
    \"\"\"
    {tool_description}

    TODO: Implement this handler.
    \"\"\"
    return f"Result for: {{input}}"
"""


class PiAgent:
    """Generate and install new skills using LLM assistance."""

    def __init__(self, workspace_path: str | None = None) -> None:
        self.workspace_path = workspace_path or "."

    def create_skill(
        self,
        description: str,
        name: str,
        provider_config: dict | None = None,
    ) -> dict:
        """
        Use LLM to generate a skill from description.
        Falls back to a template if no provider is configured.
        """
        # Sanitize skill name
        safe_name = name.lower().replace(" ", "_").replace("-", "_")
        tool_name = f"do_{safe_name}"
        tool_description = description[:120]

        # Try LLM-generated handler
        handler_code = self._generate_handler(
            name=safe_name,
            description=description,
            tool_name=tool_name,
            provider_config=provider_config,
        )

        skill_yaml = SKILL_YAML_TEMPLATE.format(
            name=safe_name,
            description=description[:80].replace('"', "'"),
            tool_name=tool_name,
            tool_description=tool_description.replace('"', "'"),
        )

        return {
            "name": safe_name,
            "tool_name": tool_name,
            "skill_yaml": skill_yaml,
            "handler_py": handler_code,
        }

    def install_skill(self, skill_data: dict) -> str:
        """Write skill files to workspace/skills/<name>/ and register."""
        name = skill_data["name"]
        skills_dir = Path(self.workspace_path) / "skills" / name
        skills_dir.mkdir(parents=True, exist_ok=True)

        (skills_dir / "skill.yaml").write_text(skill_data["skill_yaml"])
        (skills_dir / "handler.py").write_text(skill_data["handler_py"])

        # Register in global registry
        from app.skills.registry import SkillsRegistry
        SkillsRegistry.hot_reload_skill(str(skills_dir))

        logger.info("Pi-agent installed skill: %s at %s", name, skills_dir)
        return str(skills_dir)

    def _generate_handler(
        self,
        name: str,
        description: str,
        tool_name: str,
        provider_config: dict | None,
    ) -> str:
        """Attempt to generate handler code via LLM; fall back to template."""
        if not provider_config:
            return HANDLER_TEMPLATE.format(
                name=name,
                description=description,
                tool_name=tool_name,
                tool_description=description[:80],
            )

        try:
            import httpx

            api_key = provider_config.get("api_key", "")
            base_url = provider_config.get("api_base", "https://api.openai.com/v1").rstrip("/")
            model = provider_config.get("default_model", "gpt-4o-mini")

            prompt = (
                f"Write a Python handler function called `handle_{tool_name}(input: str) -> str` "
                f"that implements this skill: {description}. "
                f"Return only valid Python code, no markdown."
            )

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                },
                timeout=30,
            )
            resp.raise_for_status()
            code = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if present
            if code.startswith("```"):
                lines = code.splitlines()
                code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return code
        except Exception as exc:
            logger.warning("Pi-agent LLM generation failed: %s — using template", exc)
            return HANDLER_TEMPLATE.format(
                name=name,
                description=description,
                tool_name=tool_name,
                tool_description=description[:80],
            )
