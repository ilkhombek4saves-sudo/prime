from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BotIn(BaseModel):
    name: str
    token: str
    channels: list[str] = ["telegram"]
    allowed_user_ids: list[int] = []
    active: bool = True
    provider_defaults: dict = {}


class BotOut(BotIn):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
