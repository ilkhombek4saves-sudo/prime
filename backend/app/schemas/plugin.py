from uuid import UUID

from pydantic import BaseModel


class PluginIn(BaseModel):
    name: str
    description: str = ""
    provider_id: UUID | None = None
    command: dict | str | None = None
    allowed_bots: list[str] = []
    schema: dict = {}
    permissions: list[str] = []
    active: bool = True


class PluginOut(PluginIn):
    id: UUID

    class Config:
        from_attributes = True
