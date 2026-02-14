from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml

from app.services.config_loader import (
    BotsFile, ConfigLoader, ConfigValidationError, PluginsFile, ProvidersFile,
)

logger = logging.getLogger(__name__)


def config_hash(base_path: str = "config") -> str:
    """Compute SHA-256 hash of all YAML config files — used for optimistic concurrency."""
    base = Path(base_path)
    if not base.exists():
        return ""
    hasher = hashlib.sha256()
    for file in sorted(base.glob("*.yaml")):
        try:
            hasher.update(file.read_bytes())
        except OSError:
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


def get_config_with_hash(base_path: str = "config") -> dict[str, Any]:
    """Return config data + hash for optimistic concurrency control."""
    data = load_config(base_path)
    return {
        "config": data,
        "hash": config_hash(base_path),
        "schema": config_schema(),
    }


def apply_config(
    data: dict[str, Any],
    expected_hash: str | None = None,
    base_path: str = "config",
) -> dict[str, Any]:
    """
    Write and validate full config. Supports optimistic concurrency via expected_hash.
    Returns {"ok": True, "hash": new_hash} on success.
    Raises ValueError on hash mismatch, ConfigValidationError on bad data.
    """
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)

    # Optimistic concurrency check
    if expected_hash:
        current = config_hash(base_path)
        if current and current != expected_hash:
            raise ValueError(
                f"Config has been modified since last read. "
                f"Expected hash {expected_hash[:12]}..., current {current[:12]}..."
            )

    # Validate before writing
    loader = ConfigLoader(base_path=base_path)
    for key, model_cls in [("bots", BotsFile), ("providers", ProvidersFile), ("plugins", PluginsFile)]:
        section = data.get(key)
        if section is not None:
            model_cls.model_validate(section)

    # Write files
    for key in ("bots", "providers", "plugins"):
        section = data.get(key)
        if section is not None:
            file_path = base / f"{key}.yaml"
            file_path.write_text(yaml.dump(section, default_flow_style=False, allow_unicode=True))
            logger.info("Config file written: %s", file_path)

    new_hash = config_hash(base_path)

    # Publish config change event
    try:
        from app.services.event_bus import get_event_bus
        get_event_bus().publish_nowait("config.updated", {
            "hash": new_hash,
            "sections": list(data.keys()),
        })
    except Exception:
        pass

    return {"ok": True, "hash": new_hash}


def patch_config(
    section: str,
    patch_data: dict[str, Any],
    expected_hash: str | None = None,
    base_path: str = "config",
) -> dict[str, Any]:
    """Patch a single config section (bots/providers/plugins)."""
    if section not in ("bots", "providers", "plugins"):
        raise ValueError(f"Unknown config section: {section}")

    current = load_config(base_path)
    current_section = current.get(section, {})

    # Merge patch
    if isinstance(current_section, dict):
        current_section.update(patch_data)
    else:
        current_section = patch_data

    return apply_config({section: current_section}, expected_hash, base_path)
