from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt

from app.config.settings import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: UUID, username: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "type": "access",
        "jti": str(uuid4()),  # unique token ID — used for revocation
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    payload = _decode_token(token)
    token_type = payload.get("type")
    if token_type and token_type != "access":
        raise ValueError("Invalid access token type")

    # Check revocation blacklist
    jti = payload.get("jti")
    if jti:
        from app.auth.token_blacklist import get_blacklist
        if get_blacklist().is_revoked(jti):
            raise ValueError("Token has been revoked")

    return payload


def create_refresh_token(user_id: UUID, username: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_refresh_token(token: str) -> dict:
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token type")

    jti = payload.get("jti")
    if jti:
        from app.auth.token_blacklist import get_blacklist
        if get_blacklist().is_revoked(jti):
            raise ValueError("Refresh token has been revoked")

    return payload


def revoke_token(token: str) -> None:
    """Revoke a token by adding its JTI to the blacklist."""
    try:
        payload = _decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            from app.auth.token_blacklist import get_blacklist
            get_blacklist().revoke(jti, float(exp))
    except ValueError:
        pass  # Already invalid — nothing to revoke


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
