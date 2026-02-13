"""
Web search service with resilient research orchestration.
"""
from __future__ import annotations

from app.config.settings import get_settings
from app.services.research_engine import ResearchEngine, RotatingProxyPool


class WebSearchService:
    def __init__(self) -> None:
        settings = get_settings()
        proxies = [
            p.strip()
            for p in (settings.research_proxy_pool or "").split(",")
            if p.strip()
        ]
        self._engine = ResearchEngine(
            proxy_pool=RotatingProxyPool(proxies),
            cache_ttl_seconds=settings.research_cache_ttl_seconds,
            http_timeout_seconds=settings.research_http_timeout_seconds,
            max_retries=settings.research_max_retries,
            per_host_delay_ms=settings.research_per_host_delay_ms,
            enrich_results=settings.research_enrich_results,
        )

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str | bool]]:
        return self._engine.search(query=query, max_results=max_results)

    def format_for_context(self, results: list[dict[str, str | bool]]) -> str:
        if not results:
            return ""
        lines = ["[Актуальная информация из интернета:]"]
        for i, row in enumerate(results, 1):
            title = str(row.get("title", ""))
            url = str(row.get("href", ""))
            body = str(row.get("body", ""))[:450]
            source = str(row.get("source", "web"))
            fetched = bool(row.get("fetched", False))
            lines.append(f"\n{i}. {title}")
            if url:
                lines.append(f"   Источник: {url}")
            lines.append(f"   Канал: {source}{' + page-fetch' if fetched else ''}")
            if body:
                lines.append(f"   {body}")
        return "\n".join(lines)
