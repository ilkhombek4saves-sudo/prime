"""Tests for the base gateway adapter helpers."""
import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.gateway.base import GatewayAdapter, ResolvedContext
from app.persistence.models import (
    Agent, Bot, Binding, Provider, Session, SessionStatus, User, UserRole,
)


@pytest.fixture()
def bot(db_session):
    b = Bot(
        id=uuid.uuid4(), name="test-bot", token="tok123",
        channels=["discord"], active=True, provider_defaults={},
    )
    db_session.add(b)
    db_session.commit()
    return b


@pytest.fixture()
def provider(db_session):
    from app.persistence.models import ProviderType
    p = Provider(
        id=uuid.uuid4(), name="test-provider",
        type=ProviderType.OpenAI, active=True,
        config={"api_key": "test", "default_model": "gpt-4"},
    )
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture()
def agent(db_session, provider):
    a = Agent(
        id=uuid.uuid4(), name="test-agent",
        default_provider_id=provider.id, active=True,
        system_prompt="You are a test agent.",
        dm_policy="open", memory_enabled=False,
        group_requires_mention=False, allowed_user_ids=[],
    )
    db_session.add(a)
    db_session.commit()
    return a


def test_resolve_bot_by_name(db_session, bot):
    found = GatewayAdapter.resolve_bot(db_session, name="test-bot")
    assert found is not None
    assert found.id == bot.id


def test_resolve_bot_by_token(db_session, bot):
    found = GatewayAdapter.resolve_bot(db_session, token="tok123")
    assert found is not None
    assert found.name == "test-bot"


def test_resolve_bot_not_found(db_session):
    found = GatewayAdapter.resolve_bot(db_session, name="nonexistent")
    assert found is None


def test_get_or_create_user_new(db_session):
    user = GatewayAdapter.get_or_create_user(db_session, "new_user_123")
    assert user.username == "new_user_123"
    assert user.role == UserRole.user


def test_get_or_create_user_existing(db_session, test_user):
    user = GatewayAdapter.get_or_create_user(db_session, test_user.username)
    assert user.id == test_user.id


def test_get_or_create_session_new(db_session, bot, agent, test_user):
    session = GatewayAdapter.get_or_create_session(db_session, bot, test_user, agent)
    assert session.bot_id == bot.id
    assert session.agent_id == agent.id
    assert session.status == SessionStatus.active


def test_get_or_create_session_existing(db_session, bot, agent, test_user):
    s1 = GatewayAdapter.get_or_create_session(db_session, bot, test_user, agent)
    s2 = GatewayAdapter.get_or_create_session(db_session, bot, test_user, agent)
    assert s1.id == s2.id


def test_load_history_disabled(db_session, agent):
    agent.memory_enabled = False
    session = MagicMock()
    history = GatewayAdapter.load_history(db_session, agent, session)
    assert history == []
