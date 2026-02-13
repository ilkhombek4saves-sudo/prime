from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_role
from app.auth.security import hash_password
from app.persistence.database import get_db
from app.persistence.models import User, UserRole
from app.schemas.user import UserIn, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserOut, dependencies=[Depends(require_role("admin"))])
def create_user(payload: UserIn, db: Session = Depends(get_db)):
    user = User(
        username=payload.username,
        role=UserRole(payload.role),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-token", dependencies=[Depends(require_role("admin"))])
def reset_token(user_id: UUID, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.api_token_hash = None
    db.commit()
    return {"detail": "token reset"}
