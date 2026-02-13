"""
Analytics & cost tracking API endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.persistence.database import SessionLocal
from app.services.cost_tracker import CostTracker
from app.services.security_audit import SecurityAuditor

router = APIRouter(prefix="/analytics", tags=["analytics"])

_cost_tracker = CostTracker()
_auditor = SecurityAuditor()


@router.get("/costs/summary")
def cost_summary(days: int = Query(30, ge=1, le=365)):
    with SessionLocal() as db:
        return _cost_tracker.get_summary(db, days=days)


@router.get("/costs/by-agent")
def cost_by_agent(days: int = Query(30, ge=1, le=365)):
    with SessionLocal() as db:
        return _cost_tracker.get_by_agent(db, days=days)


@router.get("/costs/by-model")
def cost_by_model(days: int = Query(30, ge=1, le=365)):
    with SessionLocal() as db:
        return _cost_tracker.get_by_model(db, days=days)


@router.get("/security/audit")
def security_audit():
    report = _auditor.run()
    return report.to_dict()
