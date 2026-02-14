"""Tests for the idempotency service."""
import uuid
import pytest
from app.services.idempotency_service import (
    IdempotencyService,
    IdempotencyConflictError,
    IdempotencyInProgressError,
)


@pytest.fixture()
def svc(db_session):
    return IdempotencyService(db_session)


def test_reserve_new_key(svc):
    result = svc.reserve_or_get(
        key="test-key-1",
        actor_id=uuid.uuid4(),
        method="tasks.create",
        payload={"name": "hello"},
    )
    assert result is None  # New reservation returns None


def test_complete_and_get_cached(svc):
    key = "test-key-2"
    actor = uuid.uuid4()
    payload = {"x": 1}
    svc.reserve_or_get(key=key, actor_id=actor, method="m", payload=payload)
    svc.complete(key, {"result": "done"})
    cached = svc.reserve_or_get(key=key, actor_id=actor, method="m", payload=payload)
    assert cached == {"result": "done"}


def test_conflict_different_payload(svc):
    key = "conflict-key"
    actor = uuid.uuid4()
    svc.reserve_or_get(key=key, actor_id=actor, method="m", payload={"a": 1})
    svc.complete(key, {"ok": True})
    with pytest.raises(IdempotencyConflictError):
        svc.reserve_or_get(key=key, actor_id=actor, method="m", payload={"b": 2})


def test_in_progress_same_payload(svc):
    key = "progress-key"
    actor = uuid.uuid4()
    payload = {"data": "test"}
    svc.reserve_or_get(key=key, actor_id=actor, method="m", payload=payload)
    with pytest.raises(IdempotencyInProgressError):
        svc.reserve_or_get(key=key, actor_id=actor, method="m", payload=payload)


def test_fail_key(svc):
    key = "fail-key"
    actor = uuid.uuid4()
    svc.reserve_or_get(key=key, actor_id=actor, method="m", payload={})
    svc.fail(key, "something went wrong")
    # After failure, re-attempt should still see the failed state
    # (implementation-dependent — the key still exists)


def test_complete_nonexistent_key(svc):
    # Should not raise
    svc.complete("nonexistent", {"data": 1})


def test_fail_nonexistent_key(svc):
    # Should not raise
    svc.fail("nonexistent", "error")


def test_request_hash_deterministic():
    h1 = IdempotencyService._request_hash("method", {"a": 1, "b": 2})
    h2 = IdempotencyService._request_hash("method", {"b": 2, "a": 1})
    assert h1 == h2  # Sort keys ensures determinism
