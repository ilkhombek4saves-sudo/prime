"""
Tool definitions for the agentic code loop.
Two formats: OpenAI-compatible (function calling) and Anthropic (tool_use).
"""
from __future__ import annotations

import json
import os
from app.services.workspace import WorkspaceService

# ── OpenAI / OpenAI-compatible format ─────────────────────────────────────────

TOOLS_OPENAI: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a file in the agent workspace. "
                "Use this to write source code, configs, README, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path, e.g. 'src/main.py' or 'README.md'",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories in the workspace (recursive).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to list (default: workspace root)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command inside the workspace directory. "
                "Use for: installing packages, running tests, linting, building, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute, e.g. 'pip install flask'",
                    },
                },
                "required": ["command"],
            },
        },
    },
]

# ── Anthropic format ───────────────────────────────────────────────────────────

TOOLS_ANTHROPIC: list[dict] = [
    {
        "name": "write_file",
        "description": (
            "Create or overwrite a file in the agent workspace. "
            "Use this to write source code, configs, README, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path, e.g. 'src/main.py'"},
                "content": {"type": "string", "description": "Full content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "List all files and directories in the workspace (recursive).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list (default: root)"},
            },
            "required": [],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command inside the workspace directory. "
            "Use for: installing packages, running tests, linting, building, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
    },
]


_WEB_FETCH_OPENAI = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Fetch a URL and return its text content (HTML stripped to plain text, max 8000 chars).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
    },
}

_WEB_FETCH_ANTHROPIC = {
    "name": "web_fetch",
    "description": "Fetch a URL and return its text content (HTML stripped to plain text, max 8000 chars).",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
        },
        "required": ["url"],
    },
}

_SEARCH_WEB_OPENAI = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo and return top results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
}

_SEARCH_WEB_ANTHROPIC = {
    "name": "search_web",
    "description": "Search the web using DuckDuckGo and return top results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
}

TOOLS_OPENAI.append(_WEB_FETCH_OPENAI)
TOOLS_OPENAI.append(_SEARCH_WEB_OPENAI)
TOOLS_ANTHROPIC.append(_WEB_FETCH_ANTHROPIC)
TOOLS_ANTHROPIC.append(_SEARCH_WEB_ANTHROPIC)

# ── Edit tool (patch files) ──────────────────────────────────────────────────

_EDIT_FILE_OPENAI = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Edit a file by replacing exact text. The old_text must match exactly "
            "(including whitespace). Use this for precise, surgical edits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "old_text": {"type": "string", "description": "Exact text to find and replace"},
                "new_text": {"type": "string", "description": "New text to replace with"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
}

_EDIT_FILE_ANTHROPIC = {
    "name": "edit_file",
    "description": (
        "Edit a file by replacing exact text. The old_text must match exactly "
        "(including whitespace). Use this for precise, surgical edits."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "old_text": {"type": "string", "description": "Exact text to find"},
            "new_text": {"type": "string", "description": "New text to replace with"},
        },
        "required": ["path", "old_text", "new_text"],
    },
}

TOOLS_OPENAI.append(_EDIT_FILE_OPENAI)
TOOLS_ANTHROPIC.append(_EDIT_FILE_ANTHROPIC)

# ── Memory tools ─────────────────────────────────────────────────────────────

_MEMORY_SEARCH_OPENAI = {
    "type": "function",
    "function": {
        "name": "memory_search",
        "description": (
            "Search long-term memory (MEMORY.md + memory/*.md) for prior context. "
            "Use before answering questions about prior work, decisions, dates, people."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
}

_MEMORY_SEARCH_ANTHROPIC = {
    "name": "memory_search",
    "description": (
        "Search long-term memory (MEMORY.md + memory/*.md) for prior context. "
        "Use before answering questions about prior work, decisions, dates, people."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
}

_MEMORY_GET_OPENAI = {
    "type": "function",
    "function": {
        "name": "memory_get",
        "description": "Read specific lines from a memory file after memory_search.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to memory file"},
                "offset": {"type": "integer", "description": "Line number to start from (1-indexed)"},
                "limit": {"type": "integer", "description": "Max lines to read"},
            },
            "required": ["path"],
        },
    },
}

_MEMORY_GET_ANTHROPIC = {
    "name": "memory_get",
    "description": "Read specific lines from a memory file after memory_search.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to memory file"},
            "offset": {"type": "integer", "description": "Line number to start from"},
            "limit": {"type": "integer", "description": "Max lines to read"},
        },
        "required": ["path"],
    },
}

TOOLS_OPENAI.append(_MEMORY_SEARCH_OPENAI)
TOOLS_OPENAI.append(_MEMORY_GET_OPENAI)
TOOLS_ANTHROPIC.append(_MEMORY_SEARCH_ANTHROPIC)
TOOLS_ANTHROPIC.append(_MEMORY_GET_ANTHROPIC)

# ── Session management tools ─────────────────────────────────────────────────

_SESSIONS_LIST_OPENAI = {
    "type": "function",
    "function": {
        "name": "sessions_list",
        "description": "List active agent sessions with optional filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max sessions to return"},
                "active_minutes": {"type": "integer", "description": "Filter by last activity"},
            },
            "required": [],
        },
    },
}

_SESSIONS_LIST_ANTHROPIC = {
    "name": "sessions_list",
    "description": "List active agent sessions with optional filters.",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max sessions to return"},
            "active_minutes": {"type": "integer", "description": "Filter by last activity"},
        },
        "required": [],
    },
}

_SESSIONS_SEND_OPENAI = {
    "type": "function",
    "function": {
        "name": "sessions_send",
        "description": "Send a message to another session by session_key or label.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_key": {"type": "string", "description": "Target session key"},
                "message": {"type": "string", "description": "Message to send"},
            },
            "required": ["session_key", "message"],
        },
    },
}

_SESSIONS_SEND_ANTHROPIC = {
    "name": "sessions_send",
    "description": "Send a message to another session by session_key or label.",
    "input_schema": {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "Target session key"},
            "message": {"type": "string", "description": "Message to send"},
        },
        "required": ["session_key", "message"],
    },
}

_SESSIONS_SPAWN_OPENAI = {
    "type": "function",
    "function": {
        "name": "sessions_spawn",
        "description": "Spawn a background sub-agent in an isolated session.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description for the sub-agent"},
                "agent_id": {"type": "string", "description": "Optional agent ID to use"},
            },
            "required": ["task"],
        },
    },
}

_SESSIONS_SPAWN_ANTHROPIC = {
    "name": "sessions_spawn",
    "description": "Spawn a background sub-agent in an isolated session.",
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task description for the sub-agent"},
            "agent_id": {"type": "string", "description": "Optional agent ID to use"},
        },
        "required": ["task"],
    },
}

TOOLS_OPENAI.append(_SESSIONS_LIST_OPENAI)
TOOLS_OPENAI.append(_SESSIONS_SEND_OPENAI)
TOOLS_OPENAI.append(_SESSIONS_SPAWN_OPENAI)
TOOLS_ANTHROPIC.append(_SESSIONS_LIST_ANTHROPIC)
TOOLS_ANTHROPIC.append(_SESSIONS_SEND_ANTHROPIC)
TOOLS_ANTHROPIC.append(_SESSIONS_SPAWN_ANTHROPIC)

# ── Gateway control tools ────────────────────────────────────────────────────

_GATEWAY_STATUS_OPENAI = {
    "type": "function",
    "function": {
        "name": "gateway_status",
        "description": "Check gateway/cron scheduler status.",
        "parameters": {"type": "object", "properties": {}},
    },
}

_GATEWAY_STATUS_ANTHROPIC = {
    "name": "gateway_status",
    "description": "Check gateway/cron scheduler status.",
    "input_schema": {"type": "object", "properties": {}},
}

_CRON_ADD_OPENAI = {
    "type": "function",
    "function": {
        "name": "cron_add",
        "description": "Add a scheduled cron job (reminder, periodic task).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Job name"},
                "schedule": {"type": "string", "description": "Cron expression or 'every N minutes/hours'"},
                "message": {"type": "string", "description": "Message/reminder text"},
            },
            "required": ["name", "schedule", "message"],
        },
    },
}

_CRON_ADD_ANTHROPIC = {
    "name": "cron_add",
    "description": "Add a scheduled cron job (reminder, periodic task).",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Job name"},
            "schedule": {"type": "string", "description": "Cron expression or interval"},
            "message": {"type": "string", "description": "Message/reminder text"},
        },
        "required": ["name", "schedule", "message"],
    },
}

TOOLS_OPENAI.append(_GATEWAY_STATUS_OPENAI)
TOOLS_OPENAI.append(_CRON_ADD_OPENAI)
TOOLS_ANTHROPIC.append(_GATEWAY_STATUS_ANTHROPIC)
TOOLS_ANTHROPIC.append(_CRON_ADD_ANTHROPIC)

# ── Browser automation tools ─────────────────────────────────────────────────

_BROWSER_OPEN_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_open",
        "description": "Open a URL in the browser for automation.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open"},
            },
            "required": ["url"],
        },
    },
}

_BROWSER_OPEN_ANTHROPIC = {
    "name": "browser_open",
    "description": "Open a URL in the browser for automation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to open"},
        },
        "required": ["url"],
    },
}

_BROWSER_SNAPSHOT_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_snapshot",
        "description": "Capture a snapshot of the current browser page.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_page": {"type": "boolean", "description": "Capture full page"},
            },
            "required": [],
        },
    },
}

_BROWSER_SNAPSHOT_ANTHROPIC = {
    "name": "browser_snapshot",
    "description": "Capture a snapshot of the current browser page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "description": "Capture full page"},
        },
        "required": [],
    },
}

_BROWSER_CLICK_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_click",
        "description": "Click an element on the page by reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference from snapshot"},
            },
            "required": ["ref"],
        },
    },
}

_BROWSER_CLICK_ANTHROPIC = {
    "name": "browser_click",
    "description": "Click an element on the page by reference.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Element reference from snapshot"},
        },
        "required": ["ref"],
    },
}

_BROWSER_TYPE_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_type",
        "description": "Type text into an input field.",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Input element reference"},
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["ref", "text"],
        },
    },
}

_BROWSER_TYPE_ANTHROPIC = {
    "name": "browser_type",
    "description": "Type text into an input field.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Input element reference"},
            "text": {"type": "string", "description": "Text to type"},
        },
        "required": ["ref", "text"],
    },
}

TOOLS_OPENAI.append(_BROWSER_OPEN_OPENAI)
TOOLS_OPENAI.append(_BROWSER_SNAPSHOT_OPENAI)
TOOLS_OPENAI.append(_BROWSER_CLICK_OPENAI)
TOOLS_OPENAI.append(_BROWSER_TYPE_OPENAI)
TOOLS_ANTHROPIC.append(_BROWSER_OPEN_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_SNAPSHOT_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_CLICK_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_TYPE_ANTHROPIC)


def _web_fetch(url: str) -> str:
    import httpx
    try:
        import re as _re
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        text = _re.sub(r"<script[^>]*>.*?</script>", "", text, flags=_re.S)
        text = _re.sub(r"<style[^>]*>.*?</style>", "", text, flags=_re.S)
        text = _re.sub(r"<[^>]+>", " ", text)
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception as exc:
        return f"Fetch error: {exc}"


def _search_web(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"- {r.get('title', '')}: {r.get('body', '')}\n  {r.get('href', '')}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Search error: {exc}"


def _edit_file(path: str, old_text: str, new_text: str, workspace: WorkspaceService) -> str:
    """Edit a file by replacing exact text."""
    try:
        p = workspace._safe(path)
        if not p.is_file():
            return f"Error: file not found: {path}"
        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            return f"Error: old_text not found in file. Make sure it matches exactly (including whitespace)."
        new_content = content.replace(old_text, new_text, 1)
        p.write_text(new_content, encoding="utf-8")
        return f"OK: edited {path}"
    except Exception as exc:
        return f"Edit error: {exc}"


def _memory_search(query: str, max_results: int = 5) -> str:
    """Search memory files for context."""
    try:
        import glob
        from pathlib import Path
        
        memory_files = []
        workspace_root = Path(os.environ.get("PRIME_WORKSPACE", "."))
        
        # Look for MEMORY.md and memory/*.md
        memory_md = workspace_root / "MEMORY.md"
        if memory_md.exists():
            memory_files.append(memory_md)
        
        memory_dir = workspace_root / "memory"
        if memory_dir.exists():
            memory_files.extend(memory_dir.glob("*.md"))
        
        if not memory_files:
            return "No memory files found."
        
        results = []
        query_lower = query.lower()
        
        for mf in memory_files:
            try:
                content = mf.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                matches = []
                for i, line in enumerate(lines, 1):
                    if query_lower in line.lower():
                        matches.append((i, line.strip()))
                if matches:
                    results.append({
                        "path": str(mf.relative_to(workspace_root)),
                        "matches": matches[:3]  # Top 3 matches per file
                    })
            except Exception:
                continue
        
        if not results:
            return f"No matches found for: {query}"
        
        lines_out = []
        for r in results[:max_results]:
            lines_out.append(f"Source: {r['path']}")
            for line_num, line_text in r['matches']:
                lines_out.append(f"  Line {line_num}: {line_text[:100]}")
        return "\n".join(lines_out)
    except Exception as exc:
        return f"Memory search error: {exc}"


def _memory_get(path: str, offset: int = 1, limit: int = 50) -> str:
    """Read specific lines from a memory file."""
    try:
        from pathlib import Path
        workspace_root = Path(os.environ.get("PRIME_WORKSPACE", "."))
        p = workspace_root / path
        
        if not p.is_file():
            return f"Error: file not found: {path}"
        
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, offset - 1)  # Convert to 0-indexed
        end = min(len(lines), start + limit)
        
        selected = lines[start:end]
        result = f"Source: {path} (lines {start+1}-{end})\n"
        result += "\n".join(f"{i+start+1}: {line}" for i, line in enumerate(selected))
        return result
    except Exception as exc:
        return f"Memory get error: {exc}"


def _gateway_status() -> str:
    """Check gateway status."""
    return "Gateway: Prime Lite mode (gateway tools available)"


def _cron_add(name: str, schedule: str, message: str) -> str:
    """Add a cron job."""
    # Store in a simple JSON file for now
    try:
        from pathlib import Path
        import time
        
        config_dir = Path.home() / ".config" / "prime"
        config_dir.mkdir(parents=True, exist_ok=True)
        cron_file = config_dir / "cron_jobs.json"
        
        jobs = []
        if cron_file.exists():
            try:
                jobs = json.loads(cron_file.read_text())
            except:
                jobs = []
        
        job = {
            "name": name,
            "schedule": schedule,
            "message": message,
            "created_at": time.time(),
            "enabled": True
        }
        jobs.append(job)
        cron_file.write_text(json.dumps(jobs, indent=2))
        
        return f"OK: Added cron job '{name}' with schedule '{schedule}'"
    except Exception as exc:
        return f"Cron add error: {exc}"


def _browser_open(url: str) -> str:
    """Open browser (placeholder - returns info)."""
    return f"Browser: Would open {url} (browser automation requires playwright/selenium setup)"


def _browser_snapshot(full_page: bool = False) -> str:
    """Browser snapshot (placeholder)."""
    return "Browser snapshot: Not implemented in Prime Lite. Use web_fetch for static content."


def _browser_click(ref: str) -> str:
    """Browser click (placeholder)."""
    return f"Browser click: Not implemented in Prime Lite."


def _browser_type(ref: str, text: str) -> str:
    """Browser type (placeholder)."""
    return f"Browser type: Not implemented in Prime Lite."


def execute_tool(name: str, arguments: dict, workspace: WorkspaceService) -> str:
    """Dispatch a tool call to WorkspaceService and return a string result."""
    try:
        if name == "write_file":
            return workspace.write_file(arguments["path"], arguments["content"])
        if name == "read_file":
            return workspace.read_file(arguments["path"])
        if name == "list_files":
            return workspace.list_files(arguments.get("path", "."))
        if name == "run_command":
            return workspace.run_command(arguments["command"])
        if name == "web_fetch":
            return _web_fetch(arguments["url"])
        if name == "search_web":
            return _search_web(arguments["query"], arguments.get("max_results", 5))
        if name == "edit_file":
            return _edit_file(arguments["path"], arguments["old_text"], arguments["new_text"], workspace)
        if name == "memory_search":
            return _memory_search(arguments["query"], arguments.get("max_results", 5))
        if name == "memory_get":
            return _memory_get(arguments["path"], arguments.get("offset", 1), arguments.get("limit", 50))
        if name == "gateway_status":
            return _gateway_status()
        if name == "cron_add":
            return _cron_add(arguments["name"], arguments["schedule"], arguments["message"])
        if name == "browser_open":
            return _browser_open(arguments["url"])
        if name == "browser_snapshot":
            return _browser_snapshot(arguments.get("full_page", False))
        if name == "browser_click":
            return _browser_click(arguments["ref"])
        if name == "browser_type":
            return _browser_type(arguments["ref"], arguments["text"])
        if name == "sessions_list":
            return "sessions_list: Sessions managed by Prime backend."
        if name == "sessions_send":
            return f"sessions_send: Would send message to {arguments.get('session_key')}"
        if name == "sessions_spawn":
            return f"sessions_spawn: Would spawn agent for task: {arguments.get('task', '')[:50]}..."
        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"


# Export TOOLS for convenience (OpenAI format by default)
TOOLS = TOOLS_OPENAI
