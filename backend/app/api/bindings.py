from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Agent, Binding, Bot
from app.schemas.binding import BindingIn, BindingOut, BindingResolveOut
from app.services.binding_resolver import BindingResolver

router = APIRouter(prefix="/bindings", tags=["bindings"])


@router.get("", response_model=list[BindingOut])
def list_bindings(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Binding).order_by(Binding.created_at.desc()).all()


@router.post("", response_model=BindingOut)
def create_binding(
    payload: BindingIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    if not db.get(Agent, payload.agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    if payload.bot_id and not db.get(Bot, payload.bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")

    binding = Binding(**payload.model_dump())
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


@router.put("/{binding_id}", response_model=BindingOut)
def update_binding(
    binding_id: UUID,
    payload: BindingIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    binding = db.get(Binding, binding_id)
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")

    if not db.get(Agent, payload.agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    if payload.bot_id and not db.get(Bot, payload.bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")

    for field, value in payload.model_dump().items():
        setattr(binding, field, value)

    db.commit()
    db.refresh(binding)
    return binding


@router.delete("/{binding_id}")
def delete_binding(
    binding_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    binding = db.get(Binding, binding_id)
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    db.delete(binding)
    db.commit()
    return {"detail": "deleted"}


@router.get("/resolve", response_model=BindingResolveOut)
def resolve_binding(
    channel: str,
    account_id: str | None = None,
    peer: str | None = None,
    bot_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    resolver = BindingResolver(db)
    match = resolver.resolve(
        channel=channel,
        account_id=account_id,
        peer=peer,
        bot_id=bot_id,
    )
    if not match:
        return BindingResolveOut(matched=False, reason="no_matching_binding")

    return BindingResolveOut(
        matched=True,
        binding_id=match.id,
        agent_id=match.agent_id,
        reason="matched",
    )
