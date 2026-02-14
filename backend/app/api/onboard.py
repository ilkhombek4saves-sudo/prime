"""Onboard - create first admin user when no users exist."""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.persistence.database import get_db
from app.persistence.models import User, UserRole
from app.auth.security import hash_password

router = APIRouter(prefix="/onboard", tags=["onboard"])


@router.post("")
def onboard(db: Session = Depends(get_db)):
    """Create first admin user if no users exist."""
    # Check if any users exist
    user_count = db.query(func.count(User.id)).scalar()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Onboard already completed. Users exist."
        )
    
    # Create first admin user with default credentials
    # Password should be changed immediately after first login
    admin = User(
        username="admin",
        role=UserRole.admin,
        password_hash=hash_password("changeme123"),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    return {
        "message": "First admin user created",
        "username": "admin",
        "password": "changeme123",
        "warning": "Change password immediately after first login!"
    }


@router.get("/status")
def onboard_status(db: Session = Depends(get_db)):
    """Check if onboard is needed (no users exist)."""
    user_count = db.query(func.count(User.id)).scalar()
    return {
        "onboard_required": user_count == 0,
        "user_count": user_count
    }
