"""Bundled skill: web search and fetch."""
from app.skills.schema import SkillDefinition, ToolDefinition, ToolParameters

SKILL = SkillDefinition(
    name="web_search",
    version="1.0",
    description="Search the web and fetch URL content",
    tools=[
        ToolDefinition(
            name="search_web",
            description="Search the web using DuckDuckGo.",
            parameters=ToolParameters(
                properties={
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results"},
                },
                required=["query"],
            ),
        ),
        ToolDefinition(
            name="web_fetch",
            description="Fetch a URL and return its text content.",
            parameters=ToolParameters(
                properties={"url": {"type": "string", "description": "URL to fetch"}},
                required=["url"],
            ),
        ),
    ],
)


def handle_search_web(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return "\n".join(
            f"- {r.get('title', '')}: {r.get('body', '')}" for r in results
        )
    except Exception as exc:
        return f"Search error: {exc}"


def handle_web_fetch(url: str) -> str:
    import re
    import httpx
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception as exc:
        return f"Fetch error: {exc}"
