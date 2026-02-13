from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ApiMessage(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class ListResponse(BaseModel):
    items: list
    total: int


class EntityID(BaseModel):
    id: UUID
