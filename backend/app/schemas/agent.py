from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentIn(BaseModel):
    name: str
    description: str = ""
    default_provider_id: UUID | None = None
    workspace_path: str | None = None
    dm_policy: str = "pairing"
    allowed_user_ids: list[int] = []
    group_requires_mention: bool = True
    active: bool = True
    # LLM behaviour
    system_prompt: str | None = None
    web_search_enabled: bool = False
    memory_enabled: bool = True
    max_history_messages: int = 20
    code_execution_enabled: bool = False


class AgentOut(AgentIn):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
