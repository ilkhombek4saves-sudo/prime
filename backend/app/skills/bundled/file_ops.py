"""Bundled skill: file operations (read, write, list, edit)."""
from app.skills.schema import SkillDefinition, ToolDefinition, ToolParameters

SKILL = SkillDefinition(
    name="file_ops",
    version="1.0",
    description="File read/write/list/edit operations in agent workspace",
    tools=[
        ToolDefinition(
            name="read_file",
            description="Read the contents of a file from the workspace.",
            parameters=ToolParameters(
                properties={"path": {"type": "string", "description": "Relative file path"}},
                required=["path"],
            ),
        ),
        ToolDefinition(
            name="write_file",
            description="Write content to a file in the workspace.",
            parameters=ToolParameters(
                properties={
                    "path": {"type": "string", "description": "Relative file path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                required=["path", "content"],
            ),
        ),
        ToolDefinition(
            name="list_files",
            description="List files in the workspace directory.",
            parameters=ToolParameters(
                properties={"path": {"type": "string", "description": "Directory path"}},
            ),
        ),
        ToolDefinition(
            name="edit_file",
            description="Edit a file by replacing exact text.",
            parameters=ToolParameters(
                properties={
                    "path": {"type": "string", "description": "File path"},
                    "old_text": {"type": "string", "description": "Text to find"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                required=["path", "old_text", "new_text"],
            ),
        ),
    ],
)


def handle_read_file(path: str) -> str:
    from app.services.workspace import WorkspaceService
    ws = WorkspaceService(".")
    return ws.read_file(path)


def handle_write_file(path: str, content: str) -> str:
    from app.services.workspace import WorkspaceService
    ws = WorkspaceService(".")
    return ws.write_file(path, content)


def handle_list_files(path: str = ".") -> str:
    from app.services.workspace import WorkspaceService
    ws = WorkspaceService(".")
    return ws.list_files(path)


def handle_edit_file(path: str, old_text: str, new_text: str) -> str:
    from app.services.workspace import WorkspaceService
    ws = WorkspaceService(".")
    p = ws._safe(path)
    if not p.is_file():
        return f"Error: file not found: {path}"
    content = p.read_text(encoding="utf-8")
    if old_text not in content:
        return "Error: old_text not found in file"
    p.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"OK: edited {path}"
