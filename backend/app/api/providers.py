from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Provider, ProviderType
from app.providers.registry import list_supported_provider_types
from app.schemas.provider import ProviderIn, ProviderOut

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/types")
def provider_types() -> dict:
    return {"items": list_supported_provider_types()}


@router.get("", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Provider).order_by(Provider.created_at.desc()).all()


@router.post("", response_model=ProviderOut)
def create_provider(
    payload: ProviderIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    _ = user
    provider = Provider(
        name=payload.name,
        type=ProviderType(payload.type),
        config=payload.config,
        active=payload.active,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@router.put("/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: UUID,
    payload: ProviderIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.name = payload.name
    provider.type = ProviderType(payload.type)
    provider.config = payload.config
    provider.active = payload.active
    db.commit()
    db.refresh(provider)
    return provider


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _ = user
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"detail": "deleted"}
