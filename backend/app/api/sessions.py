from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Session as SessionEntity
from app.schemas.session import SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(SessionEntity).order_by(SessionEntity.created_at.desc()).all()


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    session = db.get(SessionEntity, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_key}/transcript")
async def get_session_transcript(
    session_key: str,
    user: dict = Depends(get_current_user),
):
    """Return the full message transcript for a session (DB or in-memory sub-agent)."""
    from app.services.multi_agent_service import MultiAgentService
    messages = await MultiAgentService.get_transcript(session_key)
    return {"session_key": session_key, "messages": messages}
