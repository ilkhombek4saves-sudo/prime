"""
Config RPC API — get/apply/patch config with optimistic concurrency.

GET   /api/config         — get full config + hash + schema
POST  /api/config/apply   — write full config (optional hash check)
POST  /api/config/patch   — patch a single section
POST  /api/config/validate — validate without writing
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.persistence.models import User
from app.services.config_service import (
    apply_config,
    config_hash,
    get_config_with_hash,
    load_config,
    patch_config,
)
from app.services.config_loader import ConfigLoader, ConfigValidationError

router = APIRouter(prefix="/config", tags=["config"])


class ApplyRequest(BaseModel):
    config: dict
    expected_hash: str | None = None


class PatchRequest(BaseModel):
    section: str
    data: dict
    expected_hash: str | None = None


class ValidateRequest(BaseModel):
    config: dict


@router.get("")
def get_config(current_user: User = Depends(get_current_user)):
    """Get current config with hash for optimistic concurrency."""
    return get_config_with_hash()


@router.post("/apply")
def apply_full_config(
    body: ApplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Apply full config. Pass expected_hash for optimistic concurrency."""
    try:
        result = apply_config(body.config, body.expected_hash)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/patch")
def patch_section(
    body: PatchRequest,
    current_user: User = Depends(get_current_user),
):
    """Patch a single config section (bots/providers/plugins)."""
    try:
        result = patch_config(body.section, body.data, body.expected_hash)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/validate")
def validate_config(
    body: ValidateRequest,
    current_user: User = Depends(get_current_user),
):
    """Validate config without writing to disk."""
    try:
        loader = ConfigLoader()
        # Temporarily validate the provided data
        from app.services.config_loader import BotsFile, ProvidersFile, PluginsFile
        errors = []
        for key, model_cls in [("bots", BotsFile), ("providers", ProvidersFile), ("plugins", PluginsFile)]:
            section = body.config.get(key)
            if section is not None:
                try:
                    model_cls.model_validate(section)
                except Exception as exc:
                    errors.append(f"{key}: {exc}")
        if errors:
            return {"valid": False, "errors": errors}
        return {"valid": True, "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)]}
