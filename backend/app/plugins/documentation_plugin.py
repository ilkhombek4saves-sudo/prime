from __future__ import annotations

from app.plugins.base import PluginBase


def _extract_content(result) -> str:
    if isinstance(result, dict):
        return result.get("content") or result.get("text") or str(result)
    return str(result)


class DocumentationPlugin(PluginBase):
    name = "documentation"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "required": ["project_name", "context"],
        "properties": {
            "project_name": {"type": "string", "minLength": 1},
            "context": {"type": "string", "minLength": 1},
            "doc_type": {
                "type": "string",
                "enum": ["readme", "api", "full"],
                "default": "full",
            },
        },
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        project = payload["project_name"]
        context = payload["context"]
        doc_type = payload.get("doc_type", "full")

        type_instructions = {
            "readme": "Write a comprehensive README.md with sections: Overview, Installation, Usage, Configuration, Examples.",
            "api": "Write API documentation with all endpoints, parameters, request/response examples.",
            "full": (
                "Write full project documentation including:\n"
                "1. README.md (Overview, Installation, Usage)\n"
                "2. API Reference\n"
                "3. Architecture overview\n"
                "4. Configuration guide"
            ),
        }

        prompt = (
            f"You are a technical documentation writer.\n"
            f"Project: {project}\n"
            f"Context:\n{context}\n\n"
            f"{type_instructions.get(doc_type, type_instructions['full'])}\n\n"
            f"Use Markdown formatting. Be thorough and developer-friendly."
        )

        result = self.provider.chat(prompt)
        documentation = _extract_content(result)

        return {
            "plugin": self.name,
            "project_name": project,
            "doc_type": doc_type,
            "documentation": documentation,
        }
