"""
Memory API — CRUD for persistent long-term memories.

GET    /api/memory        — list memories for the current user
POST   /api/memory        — create a new memory
DELETE /api/memory/{id}   — delete a memory
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Memory, User

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    content: str
    tags: list[str] = []
    source: str = "user_set"
    expires_at: datetime | None = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    summary: str | None
    tags: list[str]
    source: str
    expires_at: str | None
    created_at: str


def _to_response(m: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=str(m.id),
        content=m.content,
        summary=m.summary,
        tags=m.tags or [],
        source=m.source,
        expires_at=m.expires_at.isoformat() if m.expires_at else None,
        created_at=m.created_at.isoformat(),
    )


@router.get("", response_model=list[MemoryResponse])
def list_memories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(Memory)
            .where(Memory.user_id == current_user.id)
            .order_by(Memory.created_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return [_to_response(m) for m in rows]


@router.post("", response_model=MemoryResponse, status_code=201)
def create_memory(
    body: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memory = Memory(
        user_id=current_user.id,
        content=body.content,
        tags=body.tags,
        source=body.source,
        expires_at=body.expires_at,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return _to_response(memory)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(
    memory_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memory = db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(memory)
    db.commit()
