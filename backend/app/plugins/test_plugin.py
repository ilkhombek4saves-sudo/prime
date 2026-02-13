from app.plugins.base import PluginBase

__test__ = False


class TestPlugin(PluginBase):
    name = "test"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "properties": {
            "suite": {"type": "string", "enum": ["unit", "integration", "all"]},
        },
        "required": ["suite"],
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        suite = payload["suite"]
        command = "test.sh" if suite == "all" else f"test.sh {suite}"
        result = self.provider.run_cli(command)
        return {
            "plugin": self.name,
            "summary": {
                "suite": suite,
                "returncode": result.get("returncode"),
            },
            "log": {"stdout": result.get("stdout"), "stderr": result.get("stderr")},
        }
