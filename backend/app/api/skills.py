"""
Skills API — manage agent skills.

GET    /api/skills              — list all registered skills
POST   /api/skills/generate     — Pi-agent creates skill from description
DELETE /api/skills/{name}       — unregister a skill
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.persistence.models import User

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillGenerateRequest(BaseModel):
    description: str
    name: str
    workspace_path: str | None = None


class SkillResponse(BaseModel):
    name: str
    version: str
    description: str
    tools: list[str]
    path: str | None


@router.get("", response_model=list[SkillResponse])
async def list_skills(current_user: User = Depends(get_current_user)):
    from app.skills.registry import SkillsRegistry
    return [SkillResponse(**s) for s in SkillsRegistry.list_skills()]


@router.post("/generate", status_code=201)
async def generate_skill(
    body: SkillGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """Use Pi-agent to generate and install a new skill."""
    from app.skills.pi_agent import PiAgent

    pi = PiAgent(workspace_path=body.workspace_path or ".")
    skill_data = pi.create_skill(description=body.description, name=body.name)
    install_path = pi.install_skill(skill_data)
    return {
        "status": "created",
        "name": skill_data["name"],
        "path": install_path,
        "tools": [skill_data["tool_name"]],
    }


@router.delete("/{skill_name}", status_code=204)
async def delete_skill(
    skill_name: str,
    current_user: User = Depends(get_current_user),
):
    from app.skills.registry import SkillsRegistry

    skill = SkillsRegistry.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    # Remove from registry (in-memory only; files remain on disk)
    from app.skills import registry as _reg
    _reg._registry.pop(skill_name, None)
