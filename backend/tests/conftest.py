"""
Shared test fixtures for Prime backend.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force test settings before any app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-prod")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-prod")

from app.persistence.database import Base


@pytest.fixture(scope="session")
def db_engine():
    """Create a test SQLite engine, shared across the session."""
    engine = create_engine("sqlite:///test.db", connect_args={"check_same_thread": False})
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
        email="test@example.com",
        password_hash="$2b$12$testhashedpasswordvalue",
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def test_session(db_session, test_user):
    """Create a test chat session."""
    from app.persistence.models import Session as ChatSession, SessionStatus
    session = ChatSession(
        id=uuid.uuid4(),
        user_id=test_user.id,
        status=SessionStatus.active,
        title="Test session",
        meta={},
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


@pytest.fixture()
def auth_headers(test_user):
    """JWT auth headers for API requests."""
    from app.auth.security import create_token
    token = create_token({"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}
