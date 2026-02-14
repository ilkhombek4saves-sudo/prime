"""Bundled skill: whitelisted shell commands."""
from app.skills.schema import SkillDefinition, ToolDefinition, ToolParameters

SKILL = SkillDefinition(
    name="shell",
    version="1.0",
    description="Run whitelisted shell commands in agent workspace",
    tools=[
        ToolDefinition(
            name="run_command",
            description="Run a shell command in the workspace directory.",
            parameters=ToolParameters(
                properties={"command": {"type": "string", "description": "Shell command"}},
                required=["command"],
            ),
        ),
    ],
)


def handle_run_command(command: str) -> str:
    from app.services.workspace import WorkspaceService
    ws = WorkspaceService(".")
    return ws.run_command(command)
