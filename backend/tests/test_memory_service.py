"""Tests for the memory service."""
import uuid
import pytest
from app.services.memory_service import MemoryService
from app.persistence.models import Message, MessageRole, MessageType


@pytest.fixture()
def memory_svc():
    return MemoryService()


def test_get_history_empty(memory_svc, db_session, test_session):
    history = memory_svc.get_history(db_session, test_session.id)
    assert history == []


def test_save_and_get_history(memory_svc, db_session, test_session):
    memory_svc.save_exchange(
        db_session, test_session.id,
        user_text="Hello",
        assistant_text="Hi there!",
    )
    history = memory_svc.get_history(db_session, test_session.id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi there!"


def test_get_history_respects_limit(memory_svc, db_session, test_session):
    for i in range(10):
        memory_svc.save_exchange(
            db_session, test_session.id,
            user_text=f"User {i}",
            assistant_text=f"Bot {i}",
        )
    history = memory_svc.get_history(db_session, test_session.id, max_messages=4)
    assert len(history) == 4


def test_get_history_order(memory_svc, db_session, test_session):
    memory_svc.save_exchange(db_session, test_session.id, "First", "Reply 1")
    memory_svc.save_exchange(db_session, test_session.id, "Second", "Reply 2")
    history = memory_svc.get_history(db_session, test_session.id)
    assert history[0]["content"] == "First"
    assert history[-1]["content"] == "Reply 2"
