from datetime import datetime, timezone

from fastapi import APIRouter

from app.monitoring.metrics import metrics_response
from app.persistence.database import engine
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz() -> dict:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
def metrics():
    return metrics_response()
