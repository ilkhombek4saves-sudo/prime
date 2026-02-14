"""
Shared test fixtures for Prime backend.
"""
import os
import uuid

import pytest
from sqlalchemy import ARRAY, JSON, create_engine
from sqlalchemy.orm import Session

# Force test settings before any app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-prod")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-prod")

# Import Base and ALL models so they register with metadata
from app.persistence.database import Base
import app.persistence.models  # noqa: F401 — registers all models


def _patch_array_for_sqlite():
    """Replace PostgreSQL ARRAY columns with JSON for SQLite compatibility."""
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, ARRAY):
                col.type = JSON()


_patch_array_for_sqlite()


@pytest.fixture(scope="session")
def db_engine():
    """Create a test SQLite engine, shared across the session."""
    engine = create_engine(
        "sqlite:///test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    """Per-test DB session with automatic rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def test_user(db_session):
    """Create a test user in the DB."""
    from app.persistence.models import User, UserRole
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        password_hash="$2b$12$testhashedpasswordvalue",
        role=UserRole.admin,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def test_bot(db_session):
    """Create a test bot in the DB."""
    from app.persistence.models import Bot
    bot = Bot(
        id=uuid.uuid4(),
        name=f"test-bot-{uuid.uuid4().hex[:8]}",
        token="test-token",
        active=True,
    )
    db_session.add(bot)
    db_session.commit()
    return bot


@pytest.fixture()
def test_session(db_session, test_user, test_bot):
    """Create a test chat session."""
    from app.persistence.models import Session as ChatSession, SessionStatus
    session = ChatSession(
        id=uuid.uuid4(),
        bot_id=test_bot.id,
        user_id=test_user.id,
        status=SessionStatus.active,
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture()
def api_client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
