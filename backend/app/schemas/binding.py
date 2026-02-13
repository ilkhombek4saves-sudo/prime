from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BindingIn(BaseModel):
    agent_id: UUID
    bot_id: UUID | None = None
    channel: str
    account_id: str | None = None
    peer: str | None = None
    priority: int = 100
    active: bool = True


class BindingOut(BindingIn):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BindingResolveOut(BaseModel):
    matched: bool
    binding_id: UUID | None = None
    agent_id: UUID | None = None
    reason: str
