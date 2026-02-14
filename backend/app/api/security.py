"""
Security API — expose SecurityAuditor via REST.
GET /api/security/audit  — run security audit, return report
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.persistence.models import User
from app.services.security_audit import SecurityAuditor

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/audit")
def security_audit(current_user: User = Depends(get_current_user)):
    """Run automated security audit and return findings."""
    report = SecurityAuditor().run()
    return report.to_dict()
