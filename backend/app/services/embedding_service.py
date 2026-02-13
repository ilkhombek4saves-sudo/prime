"""
EmbeddingService — converts text to dense vectors for semantic search.

Strategy (tried in order):
  1. OpenAI text-embedding-3-small via any configured OpenAI-compatible provider
     that has embedding support (api_base + api_key in its config).
  2. Returns None → RAGService falls back to keyword (ILIKE) search.

The service is stateless and thread-safe. It caches the first working provider
config found in the DB on first call.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


class EmbeddingService:
    _provider_config: dict[str, Any] | None = None
    _initialized: bool = False

    # ── Public API ────────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float] | None:
        """Return embedding vector or None if no embedding provider available."""
        cfg = self._get_config()
        if not cfg:
            return None
        return self._call_api(text, cfg)

    def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        cfg = self._get_config()
        if not cfg:
            return [None] * len(texts)
        results: list[list[float] | None] = []
        for text in texts:
            results.append(self._call_api(text, cfg))
        return results

    def reset(self) -> None:
        """Force re-discovery of embedding provider (call after provider config change)."""
        self._initialized = False
        self._provider_config = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _get_config(self) -> dict[str, Any] | None:
        if self._initialized:
            return self._provider_config
        self._initialized = True
        self._provider_config = self._discover_provider()
        if self._provider_config:
            logger.info("EmbeddingService: using provider %s", self._provider_config.get("name"))
        else:
            logger.warning(
                "EmbeddingService: no embedding provider found — RAG will use keyword search"
            )
        return self._provider_config

    def _discover_provider(self) -> dict[str, Any] | None:
        """Find an OpenAI-compatible provider from the DB that supports embeddings."""
        try:
            from app.persistence.database import SessionLocal
            from app.persistence.models import Provider, ProviderType

            with SessionLocal() as db:
                # Prefer OpenAI, then any OpenAI-compatible provider
                for ptype in (ProviderType.OpenAI, ProviderType.DeepSeek,
                              ProviderType.Kimi, ProviderType.Qwen, ProviderType.GLM):
                    provider = (
                        db.query(Provider)
                        .filter(Provider.type == ptype, Provider.active.is_(True))
                        .first()
                    )
                    if provider and provider.config.get("api_key"):
                        cfg = dict(provider.config)
                        cfg["name"] = provider.name
                        cfg["provider_type"] = ptype.value
                        # Use standard OpenAI embeddings endpoint
                        base = cfg.get("api_base", "https://api.openai.com/v1").rstrip("/")
                        cfg["embeddings_url"] = f"{base}/embeddings"
                        return cfg
        except Exception as exc:
            logger.warning("EmbeddingService._discover_provider error: %s", exc)
        return None

    def _call_api(self, text: str, cfg: dict[str, Any]) -> list[float] | None:
        try:
            headers = {
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {"input": text[:8000], "model": EMBEDDING_MODEL}
            with httpx.Client(timeout=30) as client:
                resp = client.post(cfg["embeddings_url"], headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data["data"][0]["embedding"]
        except Exception as exc:
            logger.warning("EmbeddingService._call_api error: %s", exc)
            return None


# Module-level singleton
_embedding_svc = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    return _embedding_svc
