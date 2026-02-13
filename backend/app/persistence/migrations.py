from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config.settings import get_settings


def run_migrations() -> None:
    """Apply DB migrations up to head."""
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"
    script_location = project_root / "alembic"

    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic config not found: {alembic_ini}")
    if not script_location.exists():
        raise RuntimeError(f"Alembic script location not found: {script_location}")

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    # Prevent env.py from calling logging.config.fileConfig() which would
    # override our JSON logger with the alembic.ini handler configuration.
    config.config_file_name = None
    command.upgrade(config, "head")
