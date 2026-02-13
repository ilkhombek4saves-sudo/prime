from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: UUID
    bot_id: UUID
    user_id: UUID
    agent_id: UUID | None
    provider_id: UUID | None
    status: str
    reasoning_content: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
