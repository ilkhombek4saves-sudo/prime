from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Bot
from app.schemas.bot import BotIn, BotOut

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("", response_model=list[BotOut])
def list_bots(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Bot).order_by(Bot.created_at.desc()).all()


@router.post("", response_model=BotOut)
def create_bot(payload: BotIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    bot = Bot(**payload.model_dump())
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


@router.put("/{bot_id}", response_model=BotOut)
def update_bot(bot_id: UUID, payload: BotIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    bot = db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    for field, value in payload.model_dump().items():
        setattr(bot, field, value)
    db.commit()
    db.refresh(bot)
    return bot


@router.delete("/{bot_id}")
def delete_bot(bot_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    bot = db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    db.delete(bot)
    db.commit()
    return {"detail": "deleted"}
