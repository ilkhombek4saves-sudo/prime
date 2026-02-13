from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.config_loader import BotsFile, ConfigLoader, PluginsFile, ProvidersFile


def config_hash(base_path: str = "config") -> str:
    base = Path(base_path)
    if not base.exists():
        return ""
    hasher = hashlib.sha256()
    for file in sorted(base.glob("*.yaml")):
        try:
            hasher.update(file.read_bytes())
        except Exception:
            continue
    return hasher.hexdigest()


def load_config(base_path: str = "config") -> dict[str, Any]:
    loader = ConfigLoader(base_path=base_path)
    return loader.load_all()


def config_schema() -> dict[str, Any]:
    return {
        "bots": BotsFile.model_json_schema(),
        "providers": ProvidersFile.model_json_schema(),
        "plugins": PluginsFile.model_json_schema(),
    }
