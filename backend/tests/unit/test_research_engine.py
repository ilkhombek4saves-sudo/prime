from __future__ import annotations

from app.services.research_engine import ResearchEngine, RotatingProxyPool


def test_proxy_pool_rotation():
    pool = RotatingProxyPool(["http://p1:8080", "http://p2:8080"])
    assert pool.next_proxy() == "http://p1:8080"
    assert pool.next_proxy() == "http://p2:8080"
    assert pool.next_proxy() == "http://p1:8080"


def test_research_engine_cache_hits():
    calls: list[str | None] = []

    def fake_search(query: str, max_results: int, proxy: str | None):
        calls.append(proxy)
        return [{"title": "A", "href": "https://example.com", "body": "B"}]

    engine = ResearchEngine(
        proxy_pool=RotatingProxyPool(["http://proxy:8080"]),
        cache_ttl_seconds=300,
        enrich_results=0,
        search_fn=fake_search,
    )

    first = engine.search("hello", max_results=3)
    second = engine.search("hello", max_results=3)
    assert len(calls) == 1
    assert first == second


def test_research_engine_retries_with_next_proxy():
    attempts: list[str | None] = []

    def fake_search(query: str, max_results: int, proxy: str | None):
        attempts.append(proxy)
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")
        return [{"title": "ok", "href": "", "body": "done"}]

    engine = ResearchEngine(
        proxy_pool=RotatingProxyPool(["http://p1", "http://p2"]),
        cache_ttl_seconds=0,
        max_retries=2,
        enrich_results=0,
        search_fn=fake_search,
    )
    result = engine.search("retry")
    assert result[0]["title"] == "ok"
    assert attempts == ["http://p1", "http://p2"]
