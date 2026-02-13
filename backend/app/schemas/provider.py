from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProviderIn(BaseModel):
    name: str
    type: str
    config: dict = {}
    active: bool = True


class ProviderOut(ProviderIn):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
