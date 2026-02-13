"""
Memory service — loads and saves conversation history per session.
History is stored in the messages table and injected into each provider call.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.persistence.models import Message, MessageRole, MessageType
from app.persistence.models import Session as ChatSession

logger = logging.getLogger(__name__)


class MemoryService:
    def get_history(
        self,
        db: DbSession,
        session_id: uuid.UUID,
        max_messages: int = 20,
    ) -> list[dict[str, str]]:
        """Return the last `max_messages` as [{"role": "user"|"assistant", "content": str}]."""
        rows = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
            .all()
        )
        result = []
        for msg in reversed(rows):
            if msg.role in (MessageRole.user, MessageRole.assistant):
                result.append({"role": msg.role.value, "content": msg.content})
        return result

    def save_exchange(
        self,
        db: DbSession,
        session_id: uuid.UUID,
        user_text: str,
        assistant_text: str,
        *,
        user_meta: dict[str, Any] | None = None,
        assistant_meta: dict[str, Any] | None = None,
        session_meta: dict[str, Any] | None = None,
    ) -> None:
        """Persist user + assistant messages atomically."""
        db.add(Message(
            session_id=session_id,
            role=MessageRole.user,
            content=user_text,
            content_type=MessageType.text,
            meta=user_meta or {},
        ))
        db.add(Message(
            session_id=session_id,
            role=MessageRole.assistant,
            content=assistant_text,
            content_type=MessageType.text,
            meta=assistant_meta or {},
        ))
        if session_meta:
            session = db.get(ChatSession, session_id)
            if session:
                merged = dict(session.reasoning_content or {})
                merged.update(session_meta)
                session.reasoning_content = merged
        db.commit()
