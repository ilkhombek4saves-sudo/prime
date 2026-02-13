from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Agent, Binding, DMPolicy
from app.schemas.agent import AgentIn, AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Agent).order_by(Agent.created_at.desc()).all()


@router.post("", response_model=AgentOut)
def create_agent(payload: AgentIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    try:
        dm_policy = DMPolicy(payload.dm_policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid dm_policy") from exc

    agent = Agent(
        name=payload.name,
        description=payload.description,
        default_provider_id=payload.default_provider_id,
        workspace_path=payload.workspace_path,
        dm_policy=dm_policy,
        allowed_user_ids=payload.allowed_user_ids,
        group_requires_mention=payload.group_requires_mention,
        active=payload.active,
        system_prompt=payload.system_prompt,
        web_search_enabled=payload.web_search_enabled,
        memory_enabled=payload.memory_enabled,
        max_history_messages=payload.max_history_messages,
        code_execution_enabled=payload.code_execution_enabled,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: UUID,
    payload: AgentIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        agent.dm_policy = DMPolicy(payload.dm_policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid dm_policy") from exc

    agent.name = payload.name
    agent.description = payload.description
    agent.default_provider_id = payload.default_provider_id
    agent.workspace_path = payload.workspace_path
    agent.allowed_user_ids = payload.allowed_user_ids
    agent.group_requires_mention = payload.group_requires_mention
    agent.active = payload.active
    agent.system_prompt = payload.system_prompt
    agent.web_search_enabled = payload.web_search_enabled
    agent.memory_enabled = payload.memory_enabled
    agent.max_history_messages = payload.max_history_messages
    agent.code_execution_enabled = payload.code_execution_enabled

    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Remove dependent bindings first to avoid FK violation
    db.query(Binding).filter(Binding.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return {"detail": "deleted"}
