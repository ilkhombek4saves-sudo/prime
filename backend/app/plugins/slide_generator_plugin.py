from __future__ import annotations

from app.plugins.base import PluginBase


def _extract_content(result) -> str:
    if isinstance(result, dict):
        return result.get("content") or result.get("text") or str(result)
    return str(result)


class SlideGeneratorPlugin(PluginBase):
    name = "slides"
    permissions = {"admin", "user"}
    input_schema = {
        "type": "object",
        "required": ["topic", "slides_count"],
        "properties": {
            "topic": {"type": "string", "minLength": 1},
            "slides_count": {"type": "integer", "minimum": 1, "maximum": 50},
            "style": {"type": "string"},
            "audience": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, payload: dict) -> dict:
        self.validate_input(payload)
        topic = payload["topic"]
        count = payload["slides_count"]
        style = payload.get("style", "clean modern professional")
        audience = payload.get("audience", "general")

        prompt = (
            f"You are a presentation designer. Create a {count}-slide deck.\n\n"
            f"Topic: {topic}\n"
            f"Style: {style}\n"
            f"Audience: {audience}\n\n"
            f"Format each slide as:\n"
            f"## Slide N: [Title]\n"
            f"**Key points:**\n"
            f"- Point 1\n"
            f"- Point 2\n"
            f"- Point 3\n"
            f"**Speaker notes:** [brief notes for presenter]\n\n"
            f"Generate all {count} slides. Make them informative and visually structured."
        )

        result = self.provider.chat(prompt)
        content = _extract_content(result)

        # Parse slide structure for structured output
        slides = self._parse_slides(content)

        return {
            "plugin": self.name,
            "topic": topic,
            "slides_count": len(slides),
            "slides": slides,
            "raw_content": content,
        }

    @staticmethod
    def _parse_slides(content: str) -> list[dict]:
        """Parse '## Slide N: Title' sections into structured dicts."""
        import re

        slides = []
        sections = re.split(r"##\s+Slide\s+\d+", content, flags=re.IGNORECASE)
        titles = re.findall(r"##\s+Slide\s+\d+:?\s*(.+)", content, flags=re.IGNORECASE)

        for i, (title, body) in enumerate(zip(titles, sections[1:]), 1):
            slides.append({
                "index": i,
                "title": title.strip(),
                "content": body.strip(),
            })

        # If parsing failed, return whole content as slide 1
        if not slides:
            slides.append({"index": 1, "title": "Content", "content": content})

        return slides
