from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.auth.security import decode_access_token
from app.gateway.protocol import ConnectMessage, ProtocolError


@dataclass
class WSIdentity:
    user_id: UUID
    username: str
    role: str
    scopes: set[str]


def _default_scopes(role: str) -> set[str]:
    if role == "admin":
        return {"*"}
    return {"health.read", "tasks.read"}


def authenticate_connect(message: ConnectMessage, expected_nonce: str) -> WSIdentity:
    if message.nonce != expected_nonce:
        raise ProtocolError(code="invalid_nonce", message="Connect nonce mismatch")

    try:
        claims = decode_access_token(message.token)
    except ValueError as exc:
        raise ProtocolError(code="auth_failed", message="Invalid access token") from exc

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
