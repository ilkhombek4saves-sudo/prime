from app.plugins.base import PluginBase


class CustomAPIPlugin(PluginBase):
    name = "custom_api"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "required": ["url", "method"],
        "properties": {
            "url": {"type": "string", "format": "uri"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
            "headers": {"type": "object"},
            "body": {"type": ["object", "array", "string", "null"]},
        },
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        result = self.provider.run_api_call(payload)
        return {"plugin": self.name, "result": result}
