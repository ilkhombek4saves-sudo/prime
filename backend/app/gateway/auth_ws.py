from __future__ import annotations

from dataclasses import dataclass
import secrets
from uuid import UUID

from app.auth.security import decode_access_token
from app.gateway.protocol import ConnectMessage, ConnectRequest, ProtocolError
from app.config.settings import get_settings


@dataclass
class WSIdentity:
    user_id: UUID
    username: str
    role: str
    scopes: set[str]


def _default_scopes(role: str) -> set[str]:
    if role == "admin":
        return {"*"}
    return {"health.read", "tasks.read", "system.read", "status.read", "config.read"}


def authenticate_connect(message: ConnectMessage | ConnectRequest, expected_nonce: str) -> WSIdentity:
    nonce = None
    if isinstance(message, ConnectMessage):
        nonce = message.nonce
    else:
        nonce = message.nonce or (message.device.nonce if message.device else None)

    if nonce is not None and nonce != expected_nonce:
        raise ProtocolError(code="invalid_nonce", message="Connect nonce mismatch")

    token: str | None = None
    password: str | None = None
    if isinstance(message, ConnectMessage):
        token = message.token
    else:
        token = message.token or (message.auth.token if message.auth else None)
        password = message.auth.password if message.auth else None

    if token:
        try:
            claims = decode_access_token(token)
        except ValueError as exc:
            raise ProtocolError(code="auth_failed", message="Invalid access token") from exc
    else:
        settings = get_settings()
        configured = settings.gateway_password or ""
        if not configured:
            raise ProtocolError(code="auth_failed", message="Gateway password auth is not configured")
        if not password:
            raise ProtocolError(code="auth_failed", message="Password is required")
        if not secrets.compare_digest(str(password), str(configured)):
            raise ProtocolError(code="auth_failed", message="Invalid gateway password")
        # Password auth is intended for operator/admin connections (OpenClaw-style).
        claims = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "username": "gateway",
            "role": "admin",
            # scopes omitted -> default_scopes(admin) = {"*"}
        }

    try:
        user_id = UUID(str(claims["sub"]))
    except Exception as exc:
        raise ProtocolError(code="auth_failed", message="Token subject is invalid") from exc

    role = str(claims.get("role", "user"))
    scope_claim = claims.get("scopes")
    if isinstance(scope_claim, list):
        scopes = set(str(item) for item in scope_claim)
    else:
        scopes = _default_scopes(role)

    return WSIdentity(
        user_id=user_id,
        username=str(claims.get("username", "unknown")),
        role=role,
        scopes=scopes,
    )


def require_scope(identity: WSIdentity, scope: str) -> None:
    if "*" in identity.scopes:
        return
    if scope not in identity.scopes:
        raise ProtocolError(code="forbidden", message=f"Scope '{scope}' is required")
