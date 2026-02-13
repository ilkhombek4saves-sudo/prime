from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.config.settings import get_settings
from app.persistence.models import DeviceAuthRequest, DeviceAuthStatus, User


@dataclass
class OAuthDeviceError(RuntimeError):
    code: str
    message: str
    status_code: int = 400

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class OAuthDeviceService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def start_flow(
        self,
        *,
        client_name: str = "prime-cli",
        scope: str = "agent:run",
    ) -> dict:
        expires_in = int(self.settings.device_auth_ttl_seconds)
        interval = max(1, int(self.settings.device_auth_poll_interval_seconds))
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)

        device_code = secrets.token_urlsafe(32)
        device_code_hash = self._hash_device_code(device_code)
        user_code = self._generate_user_code()

        record = DeviceAuthRequest(
            device_code_hash=device_code_hash,
            user_code=user_code,
            client_name=client_name[:128] if client_name else "prime-cli",
            scope=scope[:255] if scope else "",
            status=DeviceAuthStatus.pending,
            interval_seconds=interval,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.commit()

        verify_base = self.settings.app_public_url.rstrip("/")
        verification_uri = f"{verify_base}/api/auth/device/complete"
        return {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": verification_uri,
            "verification_uri_complete": f"{verification_uri}?user_code={user_code}",
            "expires_in": expires_in,
            "interval": interval,
        }

    def complete_flow(self, *, user_code: str, username: str, password: str) -> dict:
        code = self._normalize_user_code(user_code)
        record = (
            self.db.query(DeviceAuthRequest)
            .filter(DeviceAuthRequest.user_code == code)
            .first()
        )
        if not record:
            raise OAuthDeviceError(
                code="invalid_user_code",
                message="Unknown device user code",
                status_code=404,
            )
        self._ensure_not_expired(record)
        if record.status != DeviceAuthStatus.pending:
            raise OAuthDeviceError(
                code="invalid_request",
                message=f"Device code is in status '{record.status.value}'",
                status_code=409,
            )

        user = self.db.query(User).filter(User.username == username).first()
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise OAuthDeviceError(
                code="invalid_credentials",
                message="Invalid username/password",
                status_code=401,
            )

        record.status = DeviceAuthStatus.approved
        record.user_id = user.id
        record.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"detail": "approved"}

    def exchange_device_code(self, *, device_code: str) -> dict:
        if not device_code:
            raise OAuthDeviceError(
                code="invalid_request",
                message="device_code is required",
                status_code=400,
            )
        device_code_hash = self._hash_device_code(device_code)
        record = (
            self.db.query(DeviceAuthRequest)
            .filter(DeviceAuthRequest.device_code_hash == device_code_hash)
            .first()
        )
        if not record:
            raise OAuthDeviceError(
                code="invalid_grant",
                message="Unknown device_code",
                status_code=404,
            )

        self._ensure_not_expired(record)
        if record.status == DeviceAuthStatus.pending:
            raise OAuthDeviceError(
                code="authorization_pending",
                message="Authorization is pending",
                status_code=428,
            )
        if record.status == DeviceAuthStatus.denied:
            raise OAuthDeviceError(
                code="access_denied",
                message="User denied this request",
                status_code=403,
            )
        if record.status == DeviceAuthStatus.consumed:
            raise OAuthDeviceError(
                code="invalid_grant",
                message="device_code already consumed",
                status_code=409,
            )
        if record.status != DeviceAuthStatus.approved or not record.user_id:
            raise OAuthDeviceError(
                code="invalid_grant",
                message=f"Device request in invalid status '{record.status.value}'",
                status_code=409,
            )

        user = self.db.get(User, record.user_id)
        if not user:
            raise OAuthDeviceError(
                code="invalid_grant",
                message="Approved user no longer exists",
                status_code=404,
            )

        access_token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
        refresh_token = create_refresh_token(user_id=user.id, username=user.username, role=user.role.value)

        record.status = DeviceAuthStatus.consumed
        record.consumed_at = datetime.now(timezone.utc)
        self.db.commit()
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh(self, *, refresh_token: str) -> dict:
        if not refresh_token:
            raise OAuthDeviceError(
                code="invalid_request",
                message="refresh_token is required",
                status_code=400,
            )
        try:
            payload = decode_refresh_token(refresh_token)
        except ValueError as exc:
            raise OAuthDeviceError(
                code="invalid_grant",
                message="Invalid refresh token",
                status_code=401,
            ) from exc

        user = self.db.query(User).filter(User.id == payload.get("sub")).first()
        if not user:
            raise OAuthDeviceError(
                code="invalid_grant",
                message="User not found for refresh token",
                status_code=404,
            )

        return {
            "access_token": create_access_token(
                user_id=user.id,
                username=user.username,
                role=user.role.value,
            ),
            "refresh_token": create_refresh_token(
                user_id=user.id,
                username=user.username,
                role=user.role.value,
            ),
            "token_type": "bearer",
        }

    def _ensure_not_expired(self, record: DeviceAuthRequest) -> None:
        if record.expires_at < datetime.now(timezone.utc):
            if record.status != DeviceAuthStatus.expired:
                record.status = DeviceAuthStatus.expired
                self.db.commit()
            raise OAuthDeviceError(
                code="expired_token",
                message="Device authorization expired",
                status_code=410,
            )

    @staticmethod
    def _hash_device_code(device_code: str) -> str:
        return hashlib.sha256(device_code.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_user_code(user_code: str) -> str:
        normalized = (user_code or "").strip().upper().replace(" ", "")
        if "-" not in normalized and len(normalized) == 8:
            normalized = f"{normalized[:4]}-{normalized[4:]}"
        return normalized

    @staticmethod
    def _generate_user_code() -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        raw = "".join(secrets.choice(alphabet) for _ in range(8))
        return f"{raw[:4]}-{raw[4:]}"
