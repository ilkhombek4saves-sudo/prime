from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistence.models import IdempotencyKey, IdempotencyStatus


class IdempotencyConflictError(ValueError):
    """Raised when the same idempotency key is used with different payload."""


class IdempotencyInProgressError(RuntimeError):
    """Raised when the key is already reserved and still running."""


class IdempotencyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _request_hash(method: str, payload: dict[str, Any]) -> str:
        packed = json.dumps({"method": method, "payload": payload}, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(packed.encode("utf-8")).hexdigest()

    def reserve_or_get(
        self,
        key: str,
        actor_id: UUID | None,
        method: str,
        payload: dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        request_hash = self._request_hash(method=method, payload=payload)
        existing = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()

        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError("Idempotency key collision with different payload")
            if existing.status == IdempotencyStatus.completed:
                return existing.response or {}
            raise IdempotencyInProgressError("Request with this idempotency key is in progress")

        item = IdempotencyKey(
            key=key,
            actor_id=actor_id,
            method=method,
            request_hash=request_hash,
            status=IdempotencyStatus.in_progress,
            response=None,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        self.db.add(item)
        self.db.commit()
        return None

    def complete(self, key: str, response: dict[str, Any]) -> None:
        existing = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if not existing:
            return
        existing.status = IdempotencyStatus.completed
        existing.response = response
        self.db.commit()

    def fail(self, key: str, error_message: str) -> None:
        existing = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if not existing:
            return
        existing.status = IdempotencyStatus.failed
        existing.response = {"error": error_message}
        self.db.commit()
