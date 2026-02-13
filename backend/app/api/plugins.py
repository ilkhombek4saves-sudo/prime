from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Plugin
from app.plugins.registry import list_supported_plugins
from app.schemas.plugin import PluginIn, PluginOut

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("/types")
def plugin_types() -> dict:
    return {"items": list_supported_plugins()}


@router.get("", response_model=list[PluginOut])
def list_plugins(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Plugin).all()


@router.post("", response_model=PluginOut)
def create_plugin(payload: PluginIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    plugin = Plugin(**payload.model_dump())
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    return plugin


@router.put("/{plugin_id}", response_model=PluginOut)
def update_plugin(
    plugin_id: UUID, payload: PluginIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    _ = user
    plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    for field, value in payload.model_dump().items():
        setattr(plugin, field, value)
    db.commit()
    db.refresh(plugin)
    return plugin


@router.delete("/{plugin_id}")
def delete_plugin(plugin_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    db.delete(plugin)
    db.commit()
    return {"detail": "deleted"}
