from __future__ import annotations

from app.plugins.base import PluginBase, PluginExecutionError


class TranslationPlugin(PluginBase):
    name = "translation"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "required": ["source_lang", "target_lang", "text"],
        "properties": {
            "source_lang": {"type": "string", "minLength": 2},
            "target_lang": {"type": "string", "minLength": 2},
            "text": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        source = payload["source_lang"]
        target = payload["target_lang"]
        text = payload["text"]

        prompt = (
            f"You are a professional translator.\n"
            f"Translate the following text from {source} to {target}.\n"
            f"Return ONLY the translated text, no explanations.\n\n"
            f"{text}"
        )

        result = self.provider.chat(prompt)
        translated = self._extract_content(result)

        return {
            "plugin": self.name,
            "source_lang": source,
            "target_lang": target,
            "original": text,
            "translated": translated,
        }

    @staticmethod
    def _extract_content(result) -> str:
        """Extract text content from provider.chat() response (dict or str)."""
        if isinstance(result, dict):
            return result.get("content") or result.get("text") or str(result)
        return str(result)
