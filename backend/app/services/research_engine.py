from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

try:
    from ddgs import DDGS as _DDGS

    _SEARCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    try:
        from duckduckgo_search import DDGS as _DDGS  # type: ignore[no-redef]

        _SEARCH_AVAILABLE = True
    except ImportError:
        _SEARCH_AVAILABLE = False
        logger.warning("ddgs not installed; research search backend disabled")


@dataclass
class ResearchResult:
    title: str
    href: str
    body: str
    source: str = "ddgs"
    fetched: bool = False

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "title": self.title,
            "href": self.href,
            "body": self.body,
            "source": self.source,
            "fetched": self.fetched,
        }


class RotatingProxyPool:
    def __init__(self, proxies: list[str] | None = None) -> None:
        self._proxies = [p.strip() for p in (proxies or []) if p and p.strip()]
        self._idx = 0
        self._lock = threading.Lock()

    def next_proxy(self) -> str | None:
        if not self._proxies:
            return None
        with self._lock:
            proxy = self._proxies[self._idx]
            self._idx = (self._idx + 1) % len(self._proxies)
            return proxy

    def all(self) -> list[str]:
        return list(self._proxies)


class ResearchEngine:
    """
    Safe research engine for resilient web search.
    - Adds caching, retries, and optional proxy-pool rotation.
    - Intended for reliability and latency control, not anti-bot bypassing.
    """

    def __init__(
        self,
        *,
        proxy_pool: RotatingProxyPool | None = None,
        cache_ttl_seconds: int = 120,
        http_timeout_seconds: float = 12.0,
        max_retries: int = 3,
        per_host_delay_ms: int = 450,
        enrich_results: int = 2,
        search_fn=None,
    ) -> None:
        self.proxy_pool = proxy_pool or RotatingProxyPool()
        self.cache_ttl_seconds = max(0, int(cache_ttl_seconds))
        self.http_timeout_seconds = max(1.0, float(http_timeout_seconds))
        self.max_retries = max(1, int(max_retries))
        self.per_host_delay_ms = max(0, int(per_host_delay_ms))
        self.enrich_results = max(0, int(enrich_results))
        self._search_fn = search_fn
        self._cache: dict[str, tuple[float, list[dict[str, str | bool]]]] = {}
        self._cache_lock = threading.Lock()
        self._host_last_access: dict[str, float] = {}
        self._host_lock = threading.Lock()

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str | bool]]:
        cache_key = f"{query}|{max_results}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        raw_results = self._search_with_retries(query=query, max_results=max_results)
        enriched = self._enrich(raw_results)
        payload = [item.as_dict() for item in enriched]
        self._cache_put(cache_key, payload)
        return payload

    def _search_with_retries(self, *, query: str, max_results: int) -> list[ResearchResult]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            proxy = self.proxy_pool.next_proxy()
            try:
                rows = self._search_raw(query=query, max_results=max_results, proxy=proxy)
                result = []
                for row in rows:
                    result.append(
                        ResearchResult(
                            title=str(row.get("title", "")).strip(),
                            href=str(row.get("href", "")).strip(),
                            body=str(row.get("body", "")).strip(),
                            source=str(row.get("source", "ddgs")),
                            fetched=bool(row.get("fetched", False)),
                        )
                    )
                return result
            except Exception as exc:
                last_error = exc
                sleep_s = min(3.0, 0.35 * (2 ** (attempt - 1)))
                logger.warning(
                    "Research search failed (attempt=%d/%d, proxy=%s): %s",
                    attempt,
                    self.max_retries,
                    proxy or "-",
                    exc,
                )
                time.sleep(sleep_s)
        logger.warning("Research search exhausted retries: %s", last_error)
        return []

    def _search_raw(self, *, query: str, max_results: int, proxy: str | None) -> list[dict]:
        if self._search_fn:
            return list(self._search_fn(query, max_results, proxy))
        if not _SEARCH_AVAILABLE:
            return []
        ddgs_kwargs = {}
        if proxy:
            ddgs_kwargs["proxy"] = proxy
        with _DDGS(**ddgs_kwargs) as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    def _enrich(self, results: list[ResearchResult]) -> list[ResearchResult]:
        if self.enrich_results <= 0:
            return results
        enriched: list[ResearchResult] = []
        for idx, item in enumerate(results):
            if idx >= self.enrich_results:
                enriched.append(item)
                continue
            if not item.href:
                enriched.append(item)
                continue
            fetched_body = self._fetch_page_summary(item.href)
            if fetched_body:
                enriched.append(
                    ResearchResult(
                        title=item.title,
                        href=item.href,
                        body=fetched_body,
                        source=item.source,
                        fetched=True,
                    )
                )
            else:
                enriched.append(item)
        return enriched

    def _fetch_page_summary(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return ""
        self._host_delay(parsed.netloc)

        proxy = self.proxy_pool.next_proxy()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; PrimeResearch/1.0; +https://openclaw.ai)"
            )
        }
        try:
            with httpx.Client(timeout=self.http_timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, headers=headers, proxy=proxy)
                response.raise_for_status()
                html = response.text
        except Exception as exc:
            logger.debug("Fetch summary failed for %s via proxy %s: %s", url, proxy or "-", exc)
            return ""

        text = self._extract_text(html)
        return text[:700]

    def _host_delay(self, host: str) -> None:
        if self.per_host_delay_ms <= 0 or not host:
            return
        now = time.time()
        with self._host_lock:
            last_ts = self._host_last_access.get(host, 0.0)
            min_gap = self.per_host_delay_ms / 1000.0
            wait = max(0.0, min_gap - (now - last_ts))
            if wait > 0:
                time.sleep(wait)
            self._host_last_access[host] = time.time()

    @staticmethod
    def _extract_text(html: str) -> str:
        if not html:
            return ""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        no_script = re.sub(
            r"<(script|style)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        no_tags = re.sub(r"<[^>]+>", " ", no_script)
        text = re.sub(r"\s+", " ", no_tags).strip()
        if title:
            return f"{title}. {text}"
        return text

    def _cache_get(self, key: str) -> list[dict[str, str | bool]] | None:
        if self.cache_ttl_seconds <= 0:
            return None
        now = time.time()
        with self._cache_lock:
            row = self._cache.get(key)
            if not row:
                return None
            ts, value = row
            if now - ts > self.cache_ttl_seconds:
                self._cache.pop(key, None)
                return None
            return [dict(item) for item in value]

    def _cache_put(self, key: str, value: list[dict[str, str | bool]]) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        with self._cache_lock:
            self._cache[key] = (time.time(), [dict(item) for item in value])
