"""
Sandboxed file-system operations scoped to an agent's workspace directory.
All paths are resolved relative to self.root; traversal outside root is blocked.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.services.human_engine import HumanInteractionEngine


class WorkspaceService:
    def __init__(self, root: str, humanization: dict[str, Any] | None = None) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._human_engine = HumanInteractionEngine.from_config(humanization)

    def _safe(self, path: str) -> Path:
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise PermissionError(f"Path outside workspace: {path}")
        return resolved

    def write_file(self, path: str, content: str) -> str:
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: written {path} ({len(content)} chars)"

    def read_file(self, path: str) -> str:
        p = self._safe(path)
        if not p.is_file():
            return f"Error: file not found: {path}"
        txt = p.read_text(encoding="utf-8", errors="replace")
        return txt[:8000] + ("\n...[truncated]" if len(txt) > 8000 else "")

    def list_files(self, path: str = ".") -> str:
        p = self._safe(path)
        if not p.is_dir():
            return f"Error: directory not found: {path}"
        lines = []
        for item in sorted(p.rglob("*")):
            rel = item.relative_to(self.root)
            lines.append(("[dir]  " if item.is_dir() else "[file] ") + str(rel))
        return "\n".join(lines) if lines else "(empty workspace)"

    def run_command(self, command: str) -> str:
        self._human_engine.sleep_think(complexity=len(command) // 16)
        try:
            r = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.root),
                timeout=60,
            )
            out = (r.stdout + r.stderr).strip()
            self._human_engine.pace_text(out)
            if len(out) > 4000:
                out = out[:4000] + "\n...[truncated]"
            return out or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: command timed out (60s)"
        except Exception as exc:
            return f"Error: {exc}"
