from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.config.settings import get_settings
from app.schemas.settings import SettingsOut
from app.services.config_loader import ConfigLoader

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings_api(user: dict = Depends(get_current_user)) -> SettingsOut:
    _ = user
    settings = get_settings()
    return SettingsOut(app_name=settings.app_name, app_env=settings.app_env)


@router.post("/import-config")
def import_config(user: dict = Depends(get_current_user)):
    _ = user
    loader = ConfigLoader()
    loaded = loader.load_all()
    return {"detail": "loaded", "files": list(loaded.keys())}
