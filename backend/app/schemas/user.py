from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserIn(BaseModel):
    username: str
    role: str = "user"
    password: str


class UserOut(BaseModel):
    id: UUID
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
