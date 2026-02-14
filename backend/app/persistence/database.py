from collections.abc import Generator
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config.settings import get_settings

settings = get_settings()

# PostgreSQL is required for production - SQLite only allowed for tests
database_url = settings.database_url
is_test = os.environ.get("APP_ENV") == "test" or os.environ.get("PYTEST_CURRENT_TEST")

if not database_url:
    print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
    print("Please set DATABASE_URL to a PostgreSQL connection string.", file=sys.stderr)
    sys.exit(1)

if database_url.startswith("sqlite") and not is_test:
    print("ERROR: SQLite is only allowed for testing.", file=sys.stderr)
    print("Please use PostgreSQL for production: postgresql+psycopg://user:pass@localhost:5432/prime", file=sys.stderr)
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
