from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.config.settings import get_settings
from app.main import app
from app.persistence.database import SessionLocal
from app.persistence.models import User, UserRole


def _create_user(username: str, password: str) -> None:
    with SessionLocal() as db:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return
        db.add(
            User(
                username=username,
                role=UserRole.admin,
                password_hash=hash_password(password),
            )
        )
        db.commit()


def test_device_flow_end_to_end():
    if get_settings().database_url.startswith("sqlite"):
        pytest.skip("Device auth flow test requires PostgreSQL schema support")

    username = f"device-user-{uuid.uuid4().hex[:8]}"
    password = "test-pass-123"
    _create_user(username, password)

    client = TestClient(app)

    start = client.post(
        "/api/auth/device/start",
        json={"client_name": "pytest-cli", "scope": "agent:run"},
    )
    assert start.status_code == 200
    start_payload = start.json()
    assert start_payload["device_code"]
    assert start_payload["user_code"]

    pending = client.post(
        "/api/auth/device/token",
        json={"device_code": start_payload["device_code"]},
    )
    assert pending.status_code == 428
    assert pending.json()["detail"]["error"] == "authorization_pending"

    complete = client.post(
        "/api/auth/device/complete",
        json={
            "user_code": start_payload["user_code"],
            "username": username,
            "password": password,
        },
    )
    assert complete.status_code == 200

    issued = client.post(
        "/api/auth/device/token",
        json={"device_code": start_payload["device_code"]},
    )
    assert issued.status_code == 200
    tokens = issued.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    consumed = client.post(
        "/api/auth/device/token",
        json={"device_code": start_payload["device_code"]},
    )
    assert consumed.status_code == 409

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert refreshed_payload["access_token"]
    assert refreshed_payload["refresh_token"]

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {refreshed_payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == username
