from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_role
from app.persistence.database import get_db
from app.persistence.models import PairedDevice, PairingRequest, PairingStatus
from app.schemas.pairing import (
    PairedDeviceOut,
    PairingApproveByCodeIn,
    PairingDecisionIn,
    PairingRequestIn,
    PairingRequestOut,
)
from app.services.pairing_service import PairingLimitError, approve_request, create_request, find_request_by_code

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
    try:
        request = create_request(
            db,
            device_id=payload.device_id,
            channel=payload.channel,
            account_id=payload.account_id,
            peer=payload.peer,
            requested_by_user_id=payload.requested_by_user_id,
            request_meta=payload.request_meta,
            expires_in_minutes=payload.expires_in_minutes,
        )
        return request
    except PairingLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


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
    try:
        return approve_request(
            db,
            request=request,
            decided_by=UUID(user["sub"]),
            paired_user_id=payload.paired_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/requests/approve-by-code",
    response_model=PairingRequestOut,
    dependencies=[Depends(require_role("admin"))],
)
def approve_pairing_by_code(
    payload: PairingApproveByCodeIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    request = find_request_by_code(db, payload.code)
    if not request:
        raise HTTPException(status_code=404, detail="Pairing request not found")
    try:
        return approve_request(
            db,
            request=request,
            decided_by=UUID(user["sub"]),
            paired_user_id=payload.paired_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
