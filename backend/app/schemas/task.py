from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskIn(BaseModel):
    session_id: UUID
    plugin_name: str
    provider_id: UUID
    input_data: dict


class TaskOut(BaseModel):
    id: UUID
    session_id: UUID
    plugin_id: UUID
    provider_id: UUID
    status: str
    input_data: dict
    output_data: dict
    error_message: str | None
    artifacts: dict
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True
