from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.persistence.models import PairedDevice, PairingRequest, PairingStatus


_ALPHABET = string.ascii_uppercase + string.digits


class PairingLimitError(RuntimeError):
    pass


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_request(
    db: Session,
    *,
    device_id: str,
    channel: str,
    account_id: str | None,
    peer: str | None,
    requested_by_user_id: int | None,
    request_meta: dict | None = None,
    expires_in_minutes: int = 30,
    max_pending_per_user: int = 3,
    max_pending_per_peer: int = 1,
) -> PairingRequest:
    """Create pairing request with an 8-char code and limits."""
    now = _now()
    expires_at = now + timedelta(minutes=max(1, expires_in_minutes))

    # Clean up expired pending requests
    expired = (
        db.query(PairingRequest)
        .filter(PairingRequest.status == PairingStatus.pending)
        .filter(PairingRequest.expires_at < now)
        .all()
    )
    for item in expired:
        item.status = PairingStatus.expired
    if expired:
        db.commit()

    if requested_by_user_id is not None:
        pending_user = (
            db.query(PairingRequest)
            .filter(
                PairingRequest.status == PairingStatus.pending,
                PairingRequest.requested_by_user_id == requested_by_user_id,
            )
            .count()
        )
        if pending_user >= max_pending_per_user:
            raise PairingLimitError("Too many pending pairing requests for this user")

    if peer is not None:
        pending_peer = (
            db.query(PairingRequest)
            .filter(
                PairingRequest.status == PairingStatus.pending,
                PairingRequest.peer == peer,
            )
            .count()
        )
        if pending_peer >= max_pending_per_peer:
            raise PairingLimitError("Pairing request already pending for this chat")

    code = None
    for _ in range(8):
        candidate = _generate_code()
        exists = db.query(PairingRequest).filter(PairingRequest.code == candidate).first()
        if not exists:
            code = candidate
            break
    if code is None:
        raise PairingLimitError("Could not allocate pairing code")

    request = PairingRequest(
        device_id=device_id,
        channel=channel,
        account_id=account_id,
        peer=peer,
        requested_by_user_id=requested_by_user_id,
        request_meta=request_meta or {},
        expires_at=expires_at,
        code=code,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def approve_request(
    db: Session,
    *,
    request: PairingRequest,
    decided_by,
    paired_user_id: int | None = None,
) -> PairingRequest:
    if request.status != PairingStatus.pending:
        raise ValueError("Pairing request is not pending")

    request.status = PairingStatus.approved
    request.decided_at = _now()
    request.decided_by = decided_by

    paired = db.query(PairedDevice).filter(PairedDevice.device_id == request.device_id).first()
    if not paired:
        paired = PairedDevice(device_id=request.device_id, channel=request.channel)
        db.add(paired)

    paired.channel = request.channel
    paired.account_id = request.account_id
    paired.peer = request.peer
    paired.paired_user_id = paired_user_id or request.requested_by_user_id
    paired.approved_by = request.decided_by
    paired.active = True
    paired.meta = request.request_meta

    db.commit()
    db.refresh(request)
    return request


def find_request_by_code(db: Session, code: str) -> PairingRequest | None:
    return (
        db.query(PairingRequest)
        .filter(
            PairingRequest.code == code,
            PairingRequest.status == PairingStatus.pending,
        )
        .first()
    )
