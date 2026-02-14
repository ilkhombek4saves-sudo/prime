from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config.settings import get_settings
from app.services.config_loader import ConfigLoader, ConfigValidationError
from app.services.config_sync import sync_config_to_db

logger = logging.getLogger(__name__)


class ConfigWatcher:
    def __init__(self, base_path: str = "config", interval_seconds: float = 3.0) -> None:
        self._path = Path(base_path)
        self._interval = max(1.0, float(interval_seconds))
        self._task: asyncio.Task | None = None
        self._last_mtime: float = 0.0

    def _compute_mtime(self) -> float:
        if not self._path.exists():
            return 0.0
        mtimes = []
        for file in self._path.glob("*.yaml"):
            try:
                mtimes.append(file.stat().st_mtime)
            except FileNotFoundError:
                continue
        return max(mtimes) if mtimes else 0.0

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="config-watcher")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        self._last_mtime = self._compute_mtime()
        while True:
            await asyncio.sleep(self._interval)
            mtime = self._compute_mtime()
            if mtime <= self._last_mtime:
                continue
            self._last_mtime = mtime
            try:
                settings = get_settings()
                if settings.config_reload_mode == "off":
                    logger.info("Config reload disabled (mode=off)")
                    continue
                ConfigLoader().load_and_validate()
                sync_config_to_db()

                # Publish event for connected WS clients
                try:
                    from app.services.event_bus import get_event_bus
                    from app.services.config_service import config_hash
                    get_event_bus().publish_nowait("config.reloaded", {
                        "hash": config_hash(str(self._path)),
                        "mode": settings.config_reload_mode,
                    })
                except Exception:
                    pass

                if settings.config_reload_mode == "hybrid":
                    logger.info("Config reload applied (hybrid): restart recommended")
                else:
                    logger.info("Config hot-reload applied")
            except ConfigValidationError as exc:
                logger.error("Config hot-reload failed: %s", exc)
            except Exception as exc:
                logger.error("Config hot-reload error: %s", exc, exc_info=True)
