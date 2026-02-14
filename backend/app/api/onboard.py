"""Onboard - create first admin user when no users exist."""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.persistence.database import get_db
from app.persistence.models import User, UserRole
from app.auth.security import hash_password

router = APIRouter(prefix="/onboard", tags=["onboard"])


class OnboardRequest(BaseModel):
    username: str = Field(default="admin", min_length=3, max_length=50)
    password: str = Field(default="changeme123", min_length=6, max_length=100)


class OnboardResponse(BaseModel):
    message: str
    username: str
    password: str
    warning: str


@router.post("", response_model=OnboardResponse)
def onboard(payload: OnboardRequest, db: Session = Depends(get_db)):
    """Create first admin user if no users exist."""
    # Check if any users exist
    user_count = db.query(func.count(User.id)).scalar()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Onboard already completed. Users exist."
        )
    
    # Create first admin user
    admin = User(
        username=payload.username,
        role=UserRole.admin,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    return OnboardResponse(
        message="First admin user created",
        username=payload.username,
        password=payload.password,
        warning="Change password immediately after first login!"
    )


@router.get("/status")
def onboard_status(db: Session = Depends(get_db)):
    """Check if onboard is needed (no users exist)."""
    user_count = db.query(func.count(User.id)).scalar()
    return {
        "onboard_required": user_count == 0,
        "user_count": user_count
    }
