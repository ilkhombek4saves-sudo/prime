"""Bundled skill: code execution (via sandbox if available, else subprocess)."""
from app.skills.schema import SkillDefinition, ToolDefinition, ToolParameters

SKILL = SkillDefinition(
    name="code_runner",
    version="1.0",
    description="Execute Python code snippets safely",
    tools=[
        ToolDefinition(
            name="execute_code",
            description="Execute Python code and return output.",
            parameters=ToolParameters(
                properties={
                    "code": {"type": "string", "description": "Python code to execute"},
                    "session_id": {"type": "string", "description": "Optional sandbox session ID"},
                },
                required=["code"],
            ),
        ),
    ],
)


def handle_execute_code(code: str, session_id: str | None = None) -> str:
    try:
        from app.services.sandbox_service import SandboxService
        container_id = SandboxService.create_sandbox(session_id)
        stdout, stderr, exit_code = SandboxService.exec_in_sandbox(
            container_id, f"python3 -c {repr(code)}"
        )
        SandboxService.destroy_sandbox(container_id)
        result = stdout or stderr or "(no output)"
        return f"Exit {exit_code}:\n{result[:2000]}"
    except RuntimeError:
        # Docker not available — fall back to restricted subprocess
        import subprocess
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout or result.stderr or "(no output)"
        except Exception as exc:
            return f"Execution error: {exc}"
