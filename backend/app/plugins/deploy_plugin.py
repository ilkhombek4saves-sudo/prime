from app.plugins.base import PluginBase


class DeployPlugin(PluginBase):
    name = "deploy"
    permissions = {"admin"}
    input_schema = {
        "type": "object",
        "required": ["service_name", "git_branch"],
        "properties": {
            "service_name": {"type": "string", "minLength": 1},
            "git_branch": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        command = f"deploy.sh {payload['service_name']} {payload['git_branch']}"
        result = self.provider.run_cli(command)
        return {
            "plugin": self.name,
            "status": "success" if result.get("returncode", 1) == 0 else "failed",
            "log": {"stdout": result.get("stdout"), "stderr": result.get("stderr")},
        }
