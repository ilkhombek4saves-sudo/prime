from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_role
from app.persistence.database import get_db
from app.persistence.models import PairedDevice, PairingRequest, PairingStatus
from app.schemas.pairing import (
    PairedDeviceOut,
    PairingDecisionIn,
    PairingRequestIn,
    PairingRequestOut,
)

router = APIRouter(prefix="/pairing", tags=["pairing"])


@router.get("/requests", response_model=list[PairingRequestOut])
def list_pairing_requests(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(PairingRequest).order_by(PairingRequest.created_at.desc()).all()


@router.post("/requests", response_model=PairingRequestOut)
def create_pairing_request(
    payload: PairingRequestIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, payload.expires_in_minutes))
    request = PairingRequest(
        device_id=payload.device_id,
        channel=payload.channel,
        account_id=payload.account_id,
        peer=payload.peer,
        requested_by_user_id=payload.requested_by_user_id,
        request_meta=payload.request_meta,
        expires_at=expires_at,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.post(
    "/requests/{request_id}/approve",
    response_model=PairingRequestOut,
    dependencies=[Depends(require_role("admin"))],
)
def approve_pairing_request(
    request_id: UUID,
    payload: PairingDecisionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    request = db.get(PairingRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Pairing request not found")
    if request.status != PairingStatus.pending:
        raise HTTPException(status_code=400, detail="Pairing request is not pending")

    request.status = PairingStatus.approved
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by = UUID(user["sub"])

    paired = db.query(PairedDevice).filter(PairedDevice.device_id == request.device_id).first()
    if not paired:
        paired = PairedDevice(device_id=request.device_id, channel=request.channel)
        db.add(paired)

    paired.channel = request.channel
    paired.account_id = request.account_id
    paired.peer = request.peer
    paired.paired_user_id = payload.paired_user_id or request.requested_by_user_id
    paired.approved_by = request.decided_by
    paired.active = True
    paired.meta = request.request_meta

    db.commit()
    db.refresh(request)
    return request


@router.post(
    "/requests/{request_id}/reject",
    response_model=PairingRequestOut,
    dependencies=[Depends(require_role("admin"))],
)
def reject_pairing_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    request = db.get(PairingRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Pairing request not found")
    if request.status != PairingStatus.pending:
        raise HTTPException(status_code=400, detail="Pairing request is not pending")

    request.status = PairingStatus.rejected
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by = UUID(user["sub"])
    db.commit()
    db.refresh(request)
    return request


@router.get("/devices", response_model=list[PairedDeviceOut])
def list_paired_devices(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(PairedDevice).order_by(PairedDevice.created_at.desc()).all()


@router.post(
    "/devices/{device_id}/revoke",
    dependencies=[Depends(require_role("admin"))],
)
def revoke_paired_device(
    device_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    paired = db.query(PairedDevice).filter(PairedDevice.device_id == device_id).first()
    if not paired:
        raise HTTPException(status_code=404, detail="Paired device not found")

    paired.active = False
    paired.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "revoked"}
