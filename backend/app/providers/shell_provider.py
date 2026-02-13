import shlex
import subprocess
from pathlib import Path
from typing import Any

from app.providers.base import ProviderError, ServiceProvider
from app.services.human_engine import HumanInteractionEngine


class ShellProvider(ServiceProvider):
    provider_type = "Shell"

    def validate_config(self) -> None:
        allowed = self.config.get("allowed_scripts")
        if not isinstance(allowed, list) or not allowed:
            raise ProviderError("Shell provider requires non-empty allowed_scripts")

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def _resolve_script_path(self, script_name: str) -> Path:
        configured_dir = Path(str(self.config.get("scripts_dir", "/app/scripts")))
        search_paths = []
        if configured_dir.is_absolute():
            search_paths.append(configured_dir)
        else:
            search_paths.append(Path.cwd() / configured_dir)
        search_paths.append(Path.cwd() / "scripts")

        for scripts_dir in search_paths:
            candidate = scripts_dir / script_name
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise ProviderError(f"Allowed script '{script_name}' was not found in scripts directories")

    def run_cli(self, command: str, **kwargs: Any) -> dict[str, Any]:
        parts = shlex.split(command)
        if not parts:
            raise ProviderError("Command cannot be empty")

        script_name = Path(parts[0]).name
        allowed = {Path(item).name for item in self.config.get("allowed_scripts", [])}
        if script_name not in allowed:
            raise ProviderError(f"Command '{script_name}' is not in allowlist")

        script_path = self._resolve_script_path(script_name)
        args = [str(script_path), *parts[1:]]
        timeout = int(kwargs.get("timeout", self.config.get("cli_timeout_seconds", 600)))
        human_engine = HumanInteractionEngine.from_config(self.config.get("humanization"))
        think_delay_ms = human_engine.sleep_think(complexity=len(parts))

        try:
            result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"Command timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise ProviderError(f"Script not found: {script_path}") from exc

        stdout_chunks, output_pacing_ms = human_engine.pace_text(result.stdout or "")
        _stderr_chunks, stderr_pacing_ms = human_engine.pace_text(result.stderr or "")

        return {
            "provider": self.name,
            "command": command,
            "resolved_script": str(script_path),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "humanization": {
                "enabled": human_engine.profile.enabled,
                "think_delay_ms": think_delay_ms,
                "output_pacing_ms": output_pacing_ms + stderr_pacing_ms,
                "stdout_chunks": len(stdout_chunks),
            },
        }
