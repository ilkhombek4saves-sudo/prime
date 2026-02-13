from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PairingRequestIn(BaseModel):
    device_id: str
    channel: str
    account_id: str | None = None
    peer: str | None = None
    requested_by_user_id: int | None = None
    request_meta: dict = {}
    expires_in_minutes: int = 30
    code: str | None = None


class PairingRequestOut(BaseModel):
    id: UUID
    device_id: str
    channel: str
    account_id: str | None
    peer: str | None
    requested_by_user_id: int | None
    code: str | None
    status: str
    request_meta: dict
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None

    class Config:
        from_attributes = True


class PairingDecisionIn(BaseModel):
    paired_user_id: int | None = None


class PairingApproveByCodeIn(BaseModel):
    code: str
    paired_user_id: int | None = None


class PairedDeviceOut(BaseModel):
    id: UUID
    device_id: str
    channel: str
    account_id: str | None
    peer: str | None
    paired_user_id: int | None
    approved_by: UUID | None
    active: bool
    meta: dict
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None

    class Config:
        from_attributes = True
