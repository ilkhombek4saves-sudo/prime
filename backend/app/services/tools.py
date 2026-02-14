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

# ── Additional browser tools ───────────────────────────────────────────────────

_BROWSER_FILL_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_fill",
        "description": "Fill a form field with a value.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the field"},
                "value": {"type": "string", "description": "Value to fill"},
            },
            "required": ["selector", "value"],
        },
    },
}
_BROWSER_FILL_ANTHROPIC = {
    "name": "browser_fill",
    "description": "Fill a form field with a value.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector for the field"},
            "value": {"type": "string", "description": "Value to fill"},
        },
        "required": ["selector", "value"],
    },
}

_BROWSER_SCROLL_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_scroll",
        "description": "Scroll the browser page.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "description": "Scroll direction: up/down"},
                "amount": {"type": "integer", "description": "Pixels to scroll"},
            },
            "required": [],
        },
    },
}
_BROWSER_SCROLL_ANTHROPIC = {
    "name": "browser_scroll",
    "description": "Scroll the browser page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "description": "Scroll direction: up/down"},
            "amount": {"type": "integer", "description": "Pixels to scroll"},
        },
        "required": [],
    },
}

_BROWSER_NAVIGATE_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the current browser session.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
            },
            "required": ["url"],
        },
    },
}
_BROWSER_NAVIGATE_ANTHROPIC = {
    "name": "browser_navigate",
    "description": "Navigate to a URL in the current browser session.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to navigate to"},
        },
        "required": ["url"],
    },
}

_BROWSER_EXTRACT_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_extract",
        "description": "Extract text content from a page element by CSS selector.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector"},
            },
            "required": ["selector"],
        },
    },
}
_BROWSER_EXTRACT_ANTHROPIC = {
    "name": "browser_extract",
    "description": "Extract text content from a page element by CSS selector.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector"},
        },
        "required": ["selector"],
    },
}

_BROWSER_CLOSE_OPENAI = {
    "type": "function",
    "function": {
        "name": "browser_close",
        "description": "Close the current browser session.",
        "parameters": {"type": "object", "properties": {}},
    },
}
_BROWSER_CLOSE_ANTHROPIC = {
    "name": "browser_close",
    "description": "Close the current browser session.",
    "input_schema": {"type": "object", "properties": {}},
}

TOOLS_OPENAI.append(_BROWSER_FILL_OPENAI)
TOOLS_OPENAI.append(_BROWSER_SCROLL_OPENAI)
TOOLS_OPENAI.append(_BROWSER_NAVIGATE_OPENAI)
TOOLS_OPENAI.append(_BROWSER_EXTRACT_OPENAI)
TOOLS_OPENAI.append(_BROWSER_CLOSE_OPENAI)
TOOLS_ANTHROPIC.append(_BROWSER_FILL_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_SCROLL_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_NAVIGATE_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_EXTRACT_ANTHROPIC)
TOOLS_ANTHROPIC.append(_BROWSER_CLOSE_ANTHROPIC)

# ── Memory store/forget tools ─────────────────────────────────────────────────

_MEMORY_STORE_OPENAI = {
    "type": "function",
    "function": {
        "name": "memory_store",
        "description": "Store a new long-term memory entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content to store"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
            },
            "required": ["content"],
        },
    },
}
_MEMORY_STORE_ANTHROPIC = {
    "name": "memory_store",
    "description": "Store a new long-term memory entry.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Memory content to store"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
        },
        "required": ["content"],
    },
}

_MEMORY_FORGET_OPENAI = {
    "type": "function",
    "function": {
        "name": "memory_forget",
        "description": "Delete a memory entry by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "UUID of the memory to delete"},
            },
            "required": ["memory_id"],
        },
    },
}
_MEMORY_FORGET_ANTHROPIC = {
    "name": "memory_forget",
    "description": "Delete a memory entry by its ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "UUID of the memory to delete"},
        },
        "required": ["memory_id"],
    },
}

TOOLS_OPENAI.append(_MEMORY_STORE_OPENAI)
TOOLS_OPENAI.append(_MEMORY_FORGET_OPENAI)
TOOLS_ANTHROPIC.append(_MEMORY_STORE_ANTHROPIC)
TOOLS_ANTHROPIC.append(_MEMORY_FORGET_ANTHROPIC)

# ── Cron management tools ─────────────────────────────────────────────────────

_CRON_REMOVE_OPENAI = {
    "type": "function",
    "function": {
        "name": "cron_remove",
        "description": "Remove a scheduled cron job by name.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Job name to remove"},
            },
            "required": ["name"],
        },
    },
}
_CRON_REMOVE_ANTHROPIC = {
    "name": "cron_remove",
    "description": "Remove a scheduled cron job by name.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Job name to remove"},
        },
        "required": ["name"],
    },
}

_CRON_LIST_OPENAI = {
    "type": "function",
    "function": {
        "name": "cron_list",
        "description": "List all scheduled cron jobs.",
        "parameters": {"type": "object", "properties": {}},
    },
}
_CRON_LIST_ANTHROPIC = {
    "name": "cron_list",
    "description": "List all scheduled cron jobs.",
    "input_schema": {"type": "object", "properties": {}},
}

TOOLS_OPENAI.append(_CRON_REMOVE_OPENAI)
TOOLS_OPENAI.append(_CRON_LIST_OPENAI)
TOOLS_ANTHROPIC.append(_CRON_REMOVE_ANTHROPIC)
TOOLS_ANTHROPIC.append(_CRON_LIST_ANTHROPIC)

# ── Webhook tools ─────────────────────────────────────────────────────────────

_WEBHOOK_REGISTER_OPENAI = {
    "type": "function",
    "function": {
        "name": "webhook_register",
        "description": "Register an inbound webhook that triggers an agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Webhook name"},
                "path": {"type": "string", "description": "URL path (e.g. /my-hook)"},
                "message_template": {"type": "string", "description": "Message template with {{payload.field}} placeholders"},
            },
            "required": ["name", "path", "message_template"],
        },
    },
}
_WEBHOOK_REGISTER_ANTHROPIC = {
    "name": "webhook_register",
    "description": "Register an inbound webhook that triggers an agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Webhook name"},
            "path": {"type": "string", "description": "URL path (e.g. /my-hook)"},
            "message_template": {"type": "string", "description": "Message template with {{payload.field}} placeholders"},
        },
        "required": ["name", "path", "message_template"],
    },
}

_WEBHOOK_LIST_OPENAI = {
    "type": "function",
    "function": {
        "name": "webhook_list",
        "description": "List all registered webhook bindings.",
        "parameters": {"type": "object", "properties": {}},
    },
}
_WEBHOOK_LIST_ANTHROPIC = {
    "name": "webhook_list",
    "description": "List all registered webhook bindings.",
    "input_schema": {"type": "object", "properties": {}},
}

TOOLS_OPENAI.append(_WEBHOOK_REGISTER_OPENAI)
TOOLS_OPENAI.append(_WEBHOOK_LIST_OPENAI)
TOOLS_ANTHROPIC.append(_WEBHOOK_REGISTER_ANTHROPIC)
TOOLS_ANTHROPIC.append(_WEBHOOK_LIST_ANTHROPIC)

# ── Skills tools ──────────────────────────────────────────────────────────────

_SKILL_LIST_OPENAI = {
    "type": "function",
    "function": {
        "name": "skill_list",
        "description": "List all registered skills.",
        "parameters": {"type": "object", "properties": {}},
    },
}
_SKILL_LIST_ANTHROPIC = {
    "name": "skill_list",
    "description": "List all registered skills.",
    "input_schema": {"type": "object", "properties": {}},
}

_SKILL_INSTALL_OPENAI = {
    "type": "function",
    "function": {
        "name": "skill_install",
        "description": "Install a skill from a name or workspace path.",
        "parameters": {
            "type": "object",
            "properties": {
                "name_or_path": {"type": "string", "description": "Skill name or path"},
            },
            "required": ["name_or_path"],
        },
    },
}
_SKILL_INSTALL_ANTHROPIC = {
    "name": "skill_install",
    "description": "Install a skill from a name or workspace path.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name_or_path": {"type": "string", "description": "Skill name or path"},
        },
        "required": ["name_or_path"],
    },
}

_SKILL_CREATE_OPENAI = {
    "type": "function",
    "function": {
        "name": "skill_create",
        "description": "Use Pi-agent to create a new skill from a description.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What the skill should do"},
                "name": {"type": "string", "description": "Skill name (snake_case)"},
            },
            "required": ["description", "name"],
        },
    },
}
_SKILL_CREATE_ANTHROPIC = {
    "name": "skill_create",
    "description": "Use Pi-agent to create a new skill from a description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "What the skill should do"},
            "name": {"type": "string", "description": "Skill name (snake_case)"},
        },
        "required": ["description", "name"],
    },
}

TOOLS_OPENAI.append(_SKILL_LIST_OPENAI)
TOOLS_OPENAI.append(_SKILL_INSTALL_OPENAI)
TOOLS_OPENAI.append(_SKILL_CREATE_OPENAI)
TOOLS_ANTHROPIC.append(_SKILL_LIST_ANTHROPIC)
TOOLS_ANTHROPIC.append(_SKILL_INSTALL_ANTHROPIC)
TOOLS_ANTHROPIC.append(_SKILL_CREATE_ANTHROPIC)


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
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read cron jobs file: %s", exc)
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


def execute_tool(
    name: str,
    arguments: dict,
    workspace: WorkspaceService,
    *,
    session_id: str | None = None,
    agent_id: str | None = None,
) -> str:
    """Dispatch a tool call to the appropriate service and return a string result."""
    import asyncio

    def _run_async(coro):
        """Run an async coroutine from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result(timeout=60)
            return loop.run_until_complete(coro)
        except Exception as exc:
            return f"Async error: {exc}"

    try:
        # ── Core workspace tools ───────────────────────────────────────────────
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

        # ── Memory tools ───────────────────────────────────────────────────────
        if name == "memory_search":
            return _memory_search(arguments["query"], arguments.get("max_results", 5))
        if name == "memory_get":
            return _memory_get(arguments["path"], arguments.get("offset", 1), arguments.get("limit", 50))
        if name == "memory_store":
            content = arguments["content"]
            tags = arguments.get("tags", [])
            # Store in DB Memory table (async)
            try:
                from app.services.long_term_memory import store_memory
                result = _run_async(store_memory(content=content, tags=tags, session_id=session_id))
                return f"Memory stored: {result}"
            except Exception as exc:
                return f"Memory store error: {exc}"
        if name == "memory_forget":
            memory_id = arguments["memory_id"]
            try:
                from app.services.long_term_memory import forget_memory
                result = _run_async(forget_memory(memory_id=memory_id))
                return f"Memory deleted: {result}"
            except Exception as exc:
                return f"Memory forget error: {exc}"

        # ── Gateway/status tools ───────────────────────────────────────────────
        if name == "gateway_status":
            return _gateway_status()

        # ── Cron tools ─────────────────────────────────────────────────────────
        if name == "cron_add":
            try:
                from app.services.cron_service import CronService
                result = _run_async(
                    CronService.add_job(
                        name=arguments["name"],
                        schedule=arguments["schedule"],
                        message=arguments["message"],
                        agent_id=agent_id,
                    )
                )
                return f"Cron job added: {result.get('name')} [{result.get('schedule')}]"
            except Exception as exc:
                return _cron_add(arguments["name"], arguments["schedule"], arguments["message"])
        if name == "cron_remove":
            try:
                from app.services.cron_service import CronService
                jobs = _run_async(CronService.list_jobs())
                matching = [j for j in jobs if j["name"] == arguments["name"]]
                if matching:
                    _run_async(CronService.remove_job(matching[0]["id"]))
                    return f"Cron job removed: {arguments['name']}"
                return f"Cron job not found: {arguments['name']}"
            except Exception as exc:
                return f"Cron remove error: {exc}"
        if name == "cron_list":
            try:
                from app.services.cron_service import CronService
                jobs = _run_async(CronService.list_jobs())
                if not jobs:
                    return "No cron jobs scheduled."
                lines = [f"- {j['name']} [{j['schedule']}]: {j['message'][:50]}" for j in jobs]
                return "\n".join(lines)
            except Exception as exc:
                return f"Cron list error: {exc}"

        # ── Browser tools ──────────────────────────────────────────────────────
        if name == "browser_open":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.open(arguments["url"], sid)
                if "error" in result:
                    return f"Browser error: {result['error']}"
                return f"Browser opened: {arguments['url']} (session={sid})"
            except Exception as exc:
                return _browser_open(arguments["url"])

        if name == "browser_snapshot":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.snapshot(sid, arguments.get("full_page", False))
                if "error" in result:
                    return f"Browser error: {result['error']}"
                # Save base64 PNG to workspace
                png_b64 = result.get("image", "")
                if png_b64 and workspace:
                    import base64
                    import time
                    png_path = f"screenshot_{int(time.time())}.png"
                    workspace.write_file(png_path, "")
                    p = workspace._safe(png_path)
                    p.write_bytes(base64.b64decode(png_b64))
                    return f"Screenshot saved: {png_path}"
                return "Snapshot taken (no image data)"
            except Exception as exc:
                return _browser_snapshot(arguments.get("full_page", False))

        if name == "browser_click":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.click(sid, arguments["ref"])
                return result.get("status", "Clicked") if "error" not in result else f"Browser error: {result['error']}"
            except Exception as exc:
                return _browser_click(arguments["ref"])

        if name == "browser_type":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.type_text(sid, arguments["ref"], arguments["text"])
                return result.get("status", "Typed") if "error" not in result else f"Browser error: {result['error']}"
            except Exception as exc:
                return _browser_type(arguments["ref"], arguments["text"])

        if name == "browser_fill":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.fill(sid, arguments["selector"], arguments["value"])
                return result.get("status", "Filled") if "error" not in result else f"Browser error: {result['error']}"
            except Exception as exc:
                return f"Browser fill error: {exc}"

        if name == "browser_scroll":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.scroll(sid, arguments.get("direction", "down"), arguments.get("amount", 300))
                return result.get("status", "Scrolled") if "error" not in result else f"Browser error: {result['error']}"
            except Exception as exc:
                return f"Browser scroll error: {exc}"

        if name == "browser_navigate":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.navigate(sid, arguments["url"])
                return result.get("status", "Navigated") if "error" not in result else f"Browser error: {result['error']}"
            except Exception as exc:
                return f"Browser navigate error: {exc}"

        if name == "browser_extract":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                result = BrowserService.extract(sid, arguments["selector"])
                if "error" in result:
                    return f"Browser error: {result['error']}"
                return result.get("text", "(no content)")
            except Exception as exc:
                return f"Browser extract error: {exc}"

        if name == "browser_close":
            try:
                from app.services.browser_service import BrowserService
                sid = session_id or "default"
                BrowserService.close(sid)
                return "Browser session closed"
            except Exception as exc:
                return f"Browser close error: {exc}"

        # ── Sessions / multi-agent tools ───────────────────────────────────────
        if name == "sessions_list":
            try:
                from app.services.multi_agent_service import MultiAgentService
                sessions = _run_async(
                    MultiAgentService.list_sessions(
                        limit=arguments.get("limit", 20),
                        active_minutes=arguments.get("active_minutes"),
                    )
                )
                if not sessions:
                    return "No active sessions."
                lines = [f"- {s['session_key']} ({s.get('status', '?')}) [{s.get('type', '?')}]" for s in sessions]
                return "\n".join(lines)
            except Exception as exc:
                return f"Sessions list error: {exc}"

        if name == "sessions_send":
            try:
                from app.services.multi_agent_service import MultiAgentService
                result = _run_async(
                    MultiAgentService.send_to_session(
                        arguments["session_key"], arguments["message"]
                    )
                )
                return result
            except Exception as exc:
                return f"Sessions send error: {exc}"

        if name == "sessions_spawn":
            try:
                from app.services.multi_agent_service import MultiAgentService
                child_key = _run_async(
                    MultiAgentService.spawn_agent(
                        task=arguments["task"],
                        agent_id=arguments.get("agent_id", agent_id),
                        parent_session_id=session_id,
                    )
                )
                return f"Sub-agent spawned: session_key={child_key}"
            except Exception as exc:
                return f"sessions_spawn error: {exc}"

        # ── Webhook tools ──────────────────────────────────────────────────────
        if name == "webhook_register":
            try:
                from app.services.webhook_service import WebhookService
                result = _run_async(
                    WebhookService.register(
                        name=arguments["name"],
                        path=arguments["path"],
                        message_template=arguments["message_template"],
                        agent_id=agent_id,
                    )
                )
                return f"Webhook registered: {result.get('path')}"
            except Exception as exc:
                return f"Webhook register error: {exc}"

        if name == "webhook_list":
            try:
                from app.services.webhook_service import WebhookService
                bindings = _run_async(WebhookService.list_bindings())
                if not bindings:
                    return "No webhooks registered."
                lines = [f"- {b['name']}: POST /hooks{b['path']}" for b in bindings]
                return "\n".join(lines)
            except Exception as exc:
                return f"Webhook list error: {exc}"

        # ── Skills tools ───────────────────────────────────────────────────────
        if name == "skill_list":
            try:
                from app.skills.registry import SkillsRegistry
                skills = SkillsRegistry.list_skills()
                if not skills:
                    return "No skills registered."
                lines = [f"- {s['name']} v{s['version']}: {', '.join(s['tools'])}" for s in skills]
                return "\n".join(lines)
            except Exception as exc:
                return f"Skill list error: {exc}"

        if name == "skill_install":
            try:
                from app.skills.registry import SkillsRegistry
                path = arguments["name_or_path"]
                registered = SkillsRegistry.register_from_workspace(path)
                return f"Skills installed: {', '.join(registered) or 'none found'}"
            except Exception as exc:
                return f"Skill install error: {exc}"

        if name == "skill_create":
            try:
                from app.skills.pi_agent import PiAgent
                workspace_path = workspace.root if workspace else "."
                pi = PiAgent(workspace_path=str(workspace_path))
                skill_data = pi.create_skill(
                    description=arguments["description"],
                    name=arguments["name"],
                )
                path = pi.install_skill(skill_data)
                return f"Skill created and installed: {skill_data['name']} at {path}"
            except Exception as exc:
                return f"Skill create error: {exc}"

        # ── Fallback: try skill registry ───────────────────────────────────────
        try:
            from app.skills.registry import SkillsRegistry
            result = SkillsRegistry.execute_skill_tool(name, arguments)
            if result is not None:
                return result
        except Exception:
            pass

        return f"Unknown tool: {name}"

    except Exception as exc:
        return f"Tool error ({name}): {exc}"


# Export TOOLS for convenience (OpenAI format by default)
TOOLS = TOOLS_OPENAI
