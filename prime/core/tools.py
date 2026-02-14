"""Tool definitions and executor — all system interaction tools"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from prime.config.settings import settings

# ─── Tool Schema (OpenAI function-calling format) ────────────────────────────
TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read file contents. Use for any file reading request.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path (absolute or relative to workspace)"},
            "offset": {"type": "integer", "description": "Start line number (1-based)"},
            "limit": {"type": "integer", "description": "Max lines to read"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files and directories. Use when asked about files in a directory.",
        "parameters": {"type": "object", "properties": {
            "directory": {"type": "string", "description": "Directory path (default: workspace)"},
            "recursive": {"type": "boolean", "description": "List recursively (default: false)"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Edit a file by replacing exact text.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_text": {"type": "string", "description": "Exact text to find and replace"},
            "new_text": {"type": "string", "description": "Replacement text"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "exec",
        "description": "Execute a shell command. Use for ls, git, grep, find, pip, curl, etc.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "web_fetch",
        "description": "Fetch content from a URL as plain text.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max chars to return (default: 8000)"},
        }, "required": ["url"]},
    }},
    {"type": "function", "function": {
        "name": "memory_search",
        "description": "Search memory/notes files for information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default: 5)"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "memory_save",
        "description": "Save a fact or note to persistent memory.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Memory key/topic (e.g. 'user_preferences', 'project_info')"},
            "content": {"type": "string", "description": "Content to remember"},
        }, "required": ["key", "content"]},
    }},
]


# ─── Tool Executor ──────────────────────────────────────────────────────────
class ToolExecutor:
    """Executes all tool calls locally on the machine."""

    SKIP_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv",
                  ".tox", ".mypy_cache", ".pytest_cache", "dist", "build"}

    def __init__(self, workspace: str | None = None):
        self.workspace = Path(workspace or settings.WORKSPACE).resolve()

    def _resolve(self, path: str) -> Path:
        if path.startswith("/"):
            return Path(path)
        return (self.workspace / path).resolve()

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    # ── File tools ─────────────────────────────────────────────────────────
    def read_file(self, path: str, offset: int = None, limit: int = None) -> str:
        try:
            p = self._resolve(path)
            if not p.exists():
                return f"Error: File not found: {path}"
            if p.is_dir():
                return f"Error: '{path}' is a directory. Use list_files instead."
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            start = max(0, (offset or 1) - 1)
            lines = lines[start:]
            if limit:
                lines = lines[:limit]
            result = "\n".join(f"{start + i + 1:>5} | {line}" for i, line in enumerate(lines))
            if len(result) > 50000:
                result = result[:50000] + "\n...[truncated]"
            return result or "(empty file)"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def list_files(self, directory: str = None, recursive: bool = False) -> str:
        try:
            d = self._resolve(directory) if directory else self.workspace
            if not d.exists():
                return f"Error: Directory not found: {directory or str(self.workspace)}"
            if not d.is_dir():
                return f"Error: Not a directory: {directory}"
            entries = []
            if recursive:
                for item in sorted(d.rglob("*")):
                    if any(s in item.parts for s in self.SKIP_NAMES):
                        continue
                    rel = item.relative_to(d)
                    sz = ""
                    if item.is_file():
                        try:
                            sz = f"  ({self._human_size(item.stat().st_size)})"
                        except OSError:
                            sz = ""
                    entries.append(f"  {'/' if item.is_dir() else ''}{rel}{sz}")
                    if len(entries) > 300:
                        entries.append("  ...[truncated]")
                        break
            else:
                for item in sorted(d.iterdir()):
                    if item.name in self.SKIP_NAMES:
                        entries.append(f"  {item.name}/  (skipped)")
                        continue
                    if item.is_dir():
                        entries.append(f"  {item.name}/")
                    else:
                        try:
                            sz = self._human_size(item.stat().st_size)
                        except OSError:
                            sz = "?"
                        entries.append(f"  {item.name}  ({sz})")
            header = f"Directory: {d}\n{'=' * 50}\n"
            return header + "\n".join(entries) if entries else header + "  (empty)"
        except Exception as e:
            return f"Error listing {directory}: {e}"

    def write_file(self, path: str, content: str) -> str:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"OK: Written {path} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        try:
            p = self._resolve(path)
            if not p.exists():
                return f"Error: File not found: {path}"
            content = p.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error: old_text not found in {path}"
            new_content = content.replace(old_text, new_text, 1)
            p.write_text(new_content, encoding="utf-8")
            return f"OK: Edited {path}"
        except Exception as e:
            return f"Error editing {path}: {e}"

    # ── Shell tool ─────────────────────────────────────────────────────────
    def exec(self, command: str, timeout: int = 60) -> str:
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=str(self.workspace), timeout=timeout,
            )
            out = (r.stdout + r.stderr).strip()
            if len(out) > 15000:
                out = out[:15000] + "\n...[truncated]"
            return out or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    # ── Web tools ──────────────────────────────────────────────────────────
    def web_search(self, query: str, count: int = 5) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(count, 10)))
            if not results:
                return "No results found."
            lines = [f"Search results for: {query}\n"]
            for r in results:
                lines.append(f"- {r.get('title', 'No title')}")
                lines.append(f"  {r.get('body', '')[:200]}")
                lines.append(f"  URL: {r.get('href', '')}\n")
            return "\n".join(lines)
        except ImportError:
            pass
        # Fallback: curl-based search
        try:
            encoded = urllib.parse.quote(query)
            cmd = f'curl -s "https://lite.duckduckgo.com/lite/?q={encoded}" 2>/dev/null'
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]+)</a>', r.stdout)
            lines = [f"Search results for: {query}\n"]
            seen: set = set()
            for url, title in links:
                if "duckduckgo" in url or url in seen:
                    continue
                seen.add(url)
                lines.append(f"- {title.strip()}\n  URL: {url}\n")
                if len(seen) >= count:
                    break
            return "\n".join(lines) if len(lines) > 1 else f"No results for '{query}'."
        except Exception as e:
            return f"Search error: {e}"

    def web_fetch(self, url: str, max_chars: int = 8000) -> str:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script.*?</script>", "", html, flags=re.S)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
        except Exception as e:
            return f"Error fetching {url}: {e}"

    # ── Memory tools ────────────────────────────────────────────────────────
    def memory_search(self, query: str, max_results: int = 5) -> str:
        try:
            from prime.config.settings import MEMORY_DIR
            files = []
            for d in [MEMORY_DIR, self.workspace / "memory", self.workspace]:
                if d.exists():
                    files.extend(d.glob("*.md"))
                    files.extend(d.glob("MEMORY*"))
            if not files:
                return "No memory files found."
            results = []
            q = query.lower()
            for f in files:
                try:
                    content = f.read_text(errors="ignore")
                    matches = [
                        (i + 1, line[:150])
                        for i, line in enumerate(content.splitlines())
                        if q in line.lower()
                    ]
                    if matches:
                        results.append((str(f), matches[:3]))
                except Exception:
                    pass
            if not results:
                return f"No matches for '{query}'."
            lines = [f"Memory search: '{query}'\n"]
            for path, matches in results[:max_results]:
                lines.append(f"File: {path}")
                for ln, text in matches:
                    lines.append(f"  L{ln}: {text}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    def memory_save(self, key: str, content: str) -> str:
        try:
            from prime.config.settings import MEMORY_DIR
            safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
            mem_file = MEMORY_DIR / f"{safe_key}.md"
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"\n## [{timestamp}]\n{content}\n"
            if mem_file.exists():
                mem_file.write_text(mem_file.read_text() + entry)
            else:
                mem_file.write_text(f"# Memory: {key}\n{entry}")
            return f"OK: Saved to memory '{key}'"
        except Exception as e:
            return f"Error saving memory: {e}"

    # ── Dispatcher ─────────────────────────────────────────────────────────
    def execute(self, name: str, args: dict) -> str:
        """Dispatch tool call. Normalizes camelCase args to snake_case."""
        RENAMES = {
            "oldText": "old_text", "newText": "new_text",
            "maxChars": "max_chars", "maxResults": "max_results",
            "file_path": "path",
        }
        normalized = {RENAMES.get(k, k): v for k, v in args.items()}
        method = getattr(self, name, None)
        if method:
            try:
                return str(method(**normalized))
            except Exception as e:
                return f"Error executing {name}: {e}"
        return f"Unknown tool: {name}"

    async def execute_async(self, name: str, args: dict) -> str:
        """Async wrapper — runs blocking tool in thread pool."""
        return await asyncio.to_thread(self.execute, name, args)
