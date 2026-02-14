from collections.abc import Generator
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config.settings import get_settings

settings = get_settings()

# PostgreSQL is required - SQLite is not supported due to ARRAY types
database_url = settings.database_url

if not database_url or database_url.startswith("sqlite"):
    print("ERROR: PostgreSQL is required. SQLite is not supported.", file=sys.stderr)
    print("Please set DATABASE_URL to a PostgreSQL connection string.", file=sys.stderr)
    print("Example: postgresql+psycopg://user:pass@localhost:5432/prime", file=sys.stderr)
    sys.exit(1)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# Alias for clarity in services that need a sync session
SyncSessionLocal = SessionLocal
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
