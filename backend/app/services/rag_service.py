"""
RAGService — document ingestion and retrieval-augmented generation context builder.

Indexing pipeline:
  1. Parse raw bytes (PDF / DOCX / plain-text / Markdown)
  2. Split into chunks (~400 words each, 50-word overlap)
  3. Embed each chunk via EmbeddingService (or skip if unavailable)
  4. Store DocumentChunk rows in DB

Retrieval:
  - If embeddings exist: cosine similarity between query vector and stored vectors
    (computed in Python, no pgvector extension required)
  - Fallback: full-text keyword search (ILIKE) on chunk content

The context string is injected into the agent's system prompt by telegram.py.
"""
from __future__ import annotations

import io
import json
import logging
import math
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ── Chunking constants ────────────────────────────────────────────────────────
CHUNK_WORDS = 400          # ~500-600 tokens
CHUNK_OVERLAP_WORDS = 50
MAX_CHUNKS_PER_DOC = 500   # safety cap
TOP_K_DEFAULT = 5


class RAGService:
    # ── Public API ────────────────────────────────────────────────────────

    def index_document(self, db, document_id: uuid.UUID) -> None:
        """
        Full indexing pipeline for a Document row.
        Reads raw bytes from Document.meta['raw_b64'], parses, chunks, embeds, saves chunks.
        """
        from app.persistence.models import Document, DocumentChunk, DocumentStatus

        doc: Document | None = db.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.status = DocumentStatus.indexing
        db.commit()

        try:
            raw_bytes = self._load_raw_bytes(doc)
            text = self._parse_document(raw_bytes, doc.content_type, doc.filename)
            chunks = self._split_text(text)
            chunks = chunks[:MAX_CHUNKS_PER_DOC]

            from app.services.embedding_service import get_embedding_service
            emb_svc = get_embedding_service()

            # Delete old chunks if re-indexing
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

            embeddings = emb_svc.embed_batch([c for c in chunks])

            for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    knowledge_base_id=doc.knowledge_base_id,
                    chunk_index=idx,
                    content=chunk_text,
                    embedding=embedding,  # list[float] or None
                    meta={"doc_filename": doc.filename, "chunk_idx": idx},
                )
                db.add(chunk)

            doc.chunk_count = len(chunks)
            doc.status = DocumentStatus.indexed
            doc.error = None
            db.commit()
            logger.info("Indexed doc %s: %d chunks (embeddings=%s)",
                        doc.filename, len(chunks), embeddings[0] is not None if embeddings else False)

        except Exception as exc:
            logger.error("RAG indexing failed for %s: %s", document_id, exc, exc_info=True)
            doc.status = DocumentStatus.failed
            doc.error = str(exc)[:500]
            db.commit()
            raise

    def search(
        self,
        db,
        knowledge_base_id: uuid.UUID,
        query: str,
        top_k: int = TOP_K_DEFAULT,
    ) -> list[dict[str, Any]]:
        """
        Return top-k relevant chunks for the query.
        Uses cosine similarity if embeddings exist, otherwise keyword search.
        """
        from app.persistence.models import DocumentChunk

        # Try vector search first — filter out JSON-null embeddings in Python
        # (SQLAlchemy stores Python None as JSON null, not SQL NULL, for JSON columns)
        raw_chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.knowledge_base_id == knowledge_base_id)
            .limit(2000)
            .all()
        )
        chunks = [c for c in raw_chunks if isinstance(c.embedding, list)]

        if chunks:
            return self._vector_search(query, chunks, top_k)

        # Fallback: keyword search
        return self._keyword_search(db, knowledge_base_id, query, top_k)

    def search_for_agent(
        self, db, agent_id: uuid.UUID, query: str, top_k: int = TOP_K_DEFAULT
    ) -> str:
        """
        Find all active knowledge bases for an agent, search each, return formatted context.
        Returns empty string if no KB attached or no relevant chunks found.
        """
        from app.persistence.models import KnowledgeBase

        kbs = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.agent_id == agent_id, KnowledgeBase.active.is_(True))
            .all()
        )
        if not kbs:
            return ""

        all_chunks: list[dict[str, Any]] = []
        for kb in kbs:
            results = self.search(db, kb.id, query, top_k=top_k)
            for r in results:
                r["kb_name"] = kb.name
            all_chunks.extend(results)

        if not all_chunks:
            return ""

        # Sort by score desc, keep top_k overall
        all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_chunks = all_chunks[:top_k]

        lines = ["## Relevant knowledge base context\n"]
        for i, chunk in enumerate(all_chunks, 1):
            lines.append(
                f"[{i}] Source: {chunk.get('kb_name', '?')} / {chunk.get('filename', '?')}\n"
                f"{chunk['content']}\n"
            )
        return "\n".join(lines)

    # ── Document parsing ──────────────────────────────────────────────────

    def _load_raw_bytes(self, doc) -> bytes:
        """Load raw document bytes from meta['raw_b64'] or meta['raw_path']."""
        import base64
        import os

        meta = doc.meta or {}
        if "raw_b64" in meta:
            return base64.b64decode(meta["raw_b64"])
        if "raw_path" in meta:
            path = meta["raw_path"]
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read()
        raise ValueError(f"No raw content found for document {doc.id}")

    def _parse_document(self, raw: bytes, content_type: str, filename: str) -> str:
        ct = (content_type or "").lower()
        fn = (filename or "").lower()

        if "pdf" in ct or fn.endswith(".pdf"):
            return self._parse_pdf(raw)
        if "word" in ct or "docx" in ct or fn.endswith(".docx"):
            return self._parse_docx(raw)
        # Plain text, markdown, code, etc.
        for enc in ("utf-8", "latin-1", "cp1251"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _parse_pdf(self, raw: bytes) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            raise RuntimeError(
                "pypdf not installed. Add 'pypdf>=4.0' to pyproject.toml to enable PDF support."
            )

    def _parse_docx(self, raw: bytes) -> str:
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise RuntimeError(
                "python-docx not installed. Add 'python-docx>=1.0' to pyproject.toml to enable DOCX support."
            )

    # ── Text splitting ────────────────────────────────────────────────────

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        step = CHUNK_WORDS - CHUNK_OVERLAP_WORDS
        i = 0
        while i < len(words):
            chunk_words = words[i: i + CHUNK_WORDS]
            chunk_text = " ".join(chunk_words).strip()
            if chunk_text:
                chunks.append(chunk_text)
            i += step
            if i + CHUNK_OVERLAP_WORDS >= len(words):
                break

        # Add remaining words as final chunk if significant
        tail = " ".join(words[i:]).strip()
        if tail and (not chunks or tail != chunks[-1]):
            chunks.append(tail)

        return chunks

    # ── Search backends ───────────────────────────────────────────────────

    def _vector_search(
        self, query: str, chunks: list, top_k: int
    ) -> list[dict[str, Any]]:
        from app.services.embedding_service import get_embedding_service

        q_vec = get_embedding_service().embed(query)
        if q_vec is None:
            return []

        scored: list[tuple[float, Any]] = []
        for chunk in chunks:
            emb = chunk.embedding
            if emb is None:
                continue
            score = self._cosine(q_vec, emb)
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": c.content,
                "score": round(s, 4),
                "filename": (c.meta or {}).get("doc_filename", ""),
                "chunk_index": c.chunk_index,
            }
            for s, c in scored[:top_k]
        ]

    def _keyword_search(
        self, db, knowledge_base_id: uuid.UUID, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        from app.persistence.models import DocumentChunk
        from sqlalchemy import or_

        keywords = [w.strip() for w in query.split() if len(w.strip()) > 2][:8]
        if not keywords:
            return []

        filters = [
            DocumentChunk.content.ilike(f"%{kw}%") for kw in keywords
        ]
        rows = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.knowledge_base_id == knowledge_base_id,
                or_(*filters),
            )
            .limit(top_k * 3)
            .all()
        )

        # Simple scoring: count keyword hits
        def score(row) -> float:
            text = row.content.lower()
            return sum(1.0 for kw in keywords if kw.lower() in text)

        rows.sort(key=score, reverse=True)
        return [
            {
                "content": r.content,
                "score": round(score(r) / max(len(keywords), 1), 4),
                "filename": (r.meta or {}).get("doc_filename", ""),
                "chunk_index": r.chunk_index,
            }
            for r in rows[:top_k]
        ]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


# Module-level singleton
_rag_svc = RAGService()


def get_rag_service() -> RAGService:
    return _rag_svc
