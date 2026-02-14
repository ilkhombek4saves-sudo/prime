"""
Long-term memory — cross-session facts per user+agent.
Extracted automatically from conversations, injected into system prompt.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.persistence.models import UserMemory

logger = logging.getLogger(__name__)

_EXTRACT_CATEGORIES = ("preference", "fact", "instruction", "context")
_MAX_MEMORIES_PER_USER_AGENT = 200
_MAX_INJECT = 15


class LongTermMemoryService:
    def recall(
        self,
        db: DbSession,
        user_id: uuid.UUID,
        agent_id: uuid.UUID | None = None,
        query: str | None = None,
        limit: int = _MAX_INJECT,
    ) -> list[dict]:
        q = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.active.is_(True))
        )
        if agent_id:
            q = q.filter(
                (UserMemory.agent_id == agent_id) | (UserMemory.agent_id.is_(None))
            )
        if query:
            q = q.filter(UserMemory.value.ilike(f"%{query[:100]}%"))

        rows = q.order_by(UserMemory.access_count.desc(), UserMemory.updated_at.desc()).limit(limit).all()

        now = datetime.now(timezone.utc)
        for r in rows:
            r.access_count += 1
            r.last_accessed_at = now
        if rows:
            db.commit()

        return [{"key": r.key, "value": r.value, "category": r.category} for r in rows]

    def format_for_prompt(self, memories: list[dict]) -> str:
        if not memories:
            return ""
        lines = ["[Long-term memory about this user]"]
        for m in memories:
            lines.append(f"- {m['key']}: {m['value']}")
        return "\n".join(lines)

    def store(
        self,
        db: DbSession,
        user_id: uuid.UUID,
        key: str,
        value: str,
        *,
        agent_id: uuid.UUID | None = None,
        category: str = "fact",
        session_id: uuid.UUID | None = None,
        confidence: float = 1.0,
    ) -> UserMemory:
        existing = (
            db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
                UserMemory.active.is_(True),
            )
            .first()
        )
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            return existing

        count = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.active.is_(True))
            .count()
        )
        if count >= _MAX_MEMORIES_PER_USER_AGENT:
            oldest = (
                db.query(UserMemory)
                .filter(UserMemory.user_id == user_id, UserMemory.active.is_(True))
                .order_by(UserMemory.access_count.asc(), UserMemory.updated_at.asc())
                .first()
            )
            if oldest:
                oldest.active = False

        mem = UserMemory(
            user_id=user_id,
            agent_id=agent_id,
            key=key,
            value=value,
            category=category,
            confidence=confidence,
            source_session_id=session_id,
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    def extract_and_store(
        self,
        db: DbSession,
        user_id: uuid.UUID,
        agent_id: uuid.UUID | None,
        user_text: str,
        assistant_text: str,
        session_id: uuid.UUID | None = None,
    ) -> list[UserMemory]:
        stored = []
        triggers = {
            "меня зовут": "user_name",
            "my name is": "user_name",
            "я предпочитаю": "preference",
            "i prefer": "preference",
            "запомни": "instruction",
            "remember": "instruction",
            "мой язык": "language",
            "i speak": "language",
        }
        low = user_text.lower()
        for trigger, key_prefix in triggers.items():
            if trigger in low:
                mem = self.store(
                    db,
                    user_id=user_id,
                    key=f"{key_prefix}:{trigger}",
                    value=user_text[:500],
                    agent_id=agent_id,
                    category="preference" if "prefer" in trigger else "fact",
                    session_id=session_id,
                )
                stored.append(mem)
        return stored


# ── Module-level helpers used by tools.py ────────────────────────────────────


async def store_memory(
    content: str,
    tags: list[str] | None = None,
    session_id: str | None = None,
) -> str:
    """Store a new Memory record (new persistent memory table)."""
    try:
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import Memory
        import uuid

        with SyncSessionLocal() as db:
            mem = Memory(
                user_id=uuid.uuid4(),  # anonymous if no user context
                content=content,
                tags=tags or [],
                source="agent_tool",
            )
            db.add(mem)
            db.commit()
            return str(mem.id)
    except Exception as exc:
        return f"error: {exc}"


async def forget_memory(memory_id: str) -> str:
    """Delete a Memory record by ID."""
    try:
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import Memory
        import uuid

        with SyncSessionLocal() as db:
            mem = db.get(Memory, uuid.UUID(memory_id))
            if mem:
                db.delete(mem)
                db.commit()
                return f"deleted:{memory_id}"
            return f"not_found:{memory_id}"
    except Exception as exc:
        return f"error: {exc}"
