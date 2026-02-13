from __future__ import annotations

from app.plugins.base import PluginBase


def _extract_content(result) -> str:
    if isinstance(result, dict):
        return result.get("content") or result.get("text") or str(result)
    return str(result)


class UICodePlugin(PluginBase):
    name = "ui_code"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "required": ["description", "framework"],
        "properties": {
            "description": {"type": "string", "minLength": 3},
            "framework": {"type": "string", "enum": ["react", "vue", "svelte", "html"]},
            "styling": {"type": "string", "enum": ["tailwind", "css-modules", "plain-css", "none"]},
            "typescript": {"type": "boolean"},
        },
        "additionalProperties": False,
    }

    _FRAMEWORK_PROMPTS = {
        "react": "React functional component with hooks",
        "vue": "Vue 3 Composition API <script setup> component",
        "svelte": "Svelte component with reactive declarations",
        "html": "Pure HTML/CSS/JavaScript (no framework)",
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        desc = payload["description"]
        framework = payload["framework"]
        styling = payload.get("styling", "tailwind")
        use_ts = payload.get("typescript", False)

        lang = "TypeScript" if use_ts else "JavaScript"
        fw_hint = self._FRAMEWORK_PROMPTS.get(framework, framework)
        ext = self._get_extension(framework, use_ts)

        prompt = (
            f"You are an expert frontend developer.\n"
            f"Generate a complete {fw_hint} component.\n\n"
            f"Requirements: {desc}\n"
            f"Styling: {styling}\n"
            f"Language: {lang}\n\n"
            f"Rules:\n"
            f"- Output ONLY the component code, no explanations\n"
            f"- Include all necessary imports\n"
            f"- Component should be production-ready\n"
            f"- Add prop types/interfaces if TypeScript\n"
            f"- Include hover/focus states and accessibility attributes\n"
            f"- Wrap code in a single ```{framework} code block"
        )

        result = self.provider.chat(prompt)
        raw = _extract_content(result)
        code = self._extract_code_block(raw, framework)

        return {
            "plugin": self.name,
            "framework": framework,
            "typescript": use_ts,
            "files": [
                {
                    "name": f"GeneratedComponent{ext}",
                    "content": code,
                    "language": framework,
                }
            ],
        }

    @staticmethod
    def _get_extension(framework: str, typescript: bool) -> str:
        if framework == "html":
            return ".html"
        if framework == "svelte":
            return ".svelte"
        if framework == "vue":
            return ".vue"
        return ".tsx" if typescript else ".jsx"

    @staticmethod
    def _extract_code_block(text: str, framework: str) -> str:
        """Extract code from markdown code block if present."""
        import re

        patterns = [
            rf"```{framework}(.*?)```",
            r"```(?:tsx?|jsx?|html|svelte|vue)(.*?)```",
            r"```(.*?)```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return text.strip()
