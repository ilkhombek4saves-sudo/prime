import uuid

from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.config.settings import get_settings
from app.main import app


def _recv_until(ws, predicate, max_messages=10):
    for _ in range(max_messages):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("Expected message was not received")


def test_ws_connect_and_health_request():
    token = create_access_token(user_id=uuid.uuid4(), username="ws-user", role="user")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/events") as ws:
        challenge = ws.receive_json()
        assert challenge["type"] == "event"
        assert challenge["event"] == "connect.challenge"

        ws.send_json(
            {
                "type": "req",
                "id": "connect-1",
                "method": "connect",
                "params": {
                    "token": token,
                    "nonce": challenge["payload"]["nonce"],
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {"name": "pytest", "version": "1"},
                },
            }
        )

        _ = _recv_until(ws, lambda m: m.get("type") == "res" and m.get("id") == "connect-1")

        connected = _recv_until(ws, lambda m: m.get("type") == "event")
        assert connected["event"] == "presence.connected"

        ws.send_json(
            {
                "type": "req",
                "id": "req-1",
                "method": "health.get",
                "params": {},
            }
        )

        response = _recv_until(ws, lambda m: m.get("type") == "res" and m.get("id") == "req-1")
        assert response["ok"] is True
        assert response["payload"]["status"] == "ok"


def test_ws_side_effect_requires_idempotency_key():
    token = create_access_token(user_id=uuid.uuid4(), username="admin", role="admin")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/events") as ws:
        challenge = ws.receive_json()
        ws.send_json(
            {
                "type": "req",
                "id": "connect-2",
                "method": "connect",
                "params": {
                    "token": token,
                    "nonce": challenge["payload"]["nonce"],
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {"name": "pytest", "version": "1"},
                },
            }
        )

        _ = _recv_until(ws, lambda m: m.get("type") == "res" and m.get("id") == "connect-2")
        _ = _recv_until(ws, lambda m: m.get("type") == "event")

        ws.send_json(
            {
                "type": "req",
                "id": "req-2",
                "method": "tasks.retry",
                "params": {"task_id": str(uuid.uuid4())},
            }
        )

        error = _recv_until(ws, lambda m: m.get("type") == "error" and m.get("id") == "req-2")
        assert error["code"] == "idempotency_required"


def test_ws_connect_with_gateway_password(monkeypatch):
    monkeypatch.setenv("GATEWAY_PASSWORD", "test-gateway-pass")
    get_settings.cache_clear()
    client = TestClient(app)

    with client.websocket_connect("/api/ws/events") as ws:
        challenge = ws.receive_json()
        assert challenge["type"] == "event"
        assert challenge["event"] == "connect.challenge"

        ws.send_json(
            {
                "type": "req",
                "id": "connect-pass-1",
                "method": "connect",
                "params": {
                    "nonce": challenge["payload"]["nonce"],
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {"name": "pytest", "version": "1"},
                    "auth": {"password": "test-gateway-pass"},
                },
            }
        )

        res = _recv_until(ws, lambda m: m.get("type") == "res" and m.get("id") == "connect-pass-1")
        assert res["payload"]["auth"]["role"] == "admin"

        ws.send_json(
            {
                "type": "req",
                "id": "req-pass-1",
                "method": "health.get",
                "params": {},
            }
        )

        response = _recv_until(ws, lambda m: m.get("type") == "res" and m.get("id") == "req-pass-1")
        assert response["ok"] is True
        assert response["payload"]["status"] == "ok"
