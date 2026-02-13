"""
Tool definitions for the agentic code loop.
Two formats: OpenAI-compatible (function calling) and Anthropic (tool_use).
"""
from __future__ import annotations

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
        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"
