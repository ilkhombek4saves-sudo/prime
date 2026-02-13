from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import get_db
from app.persistence.models import Task
from app.schemas.task import TaskIn, TaskOut
from app.services.command_bus import CommandBus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    return db.query(Task).order_by(Task.created_at.desc()).all()


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskOut)
def create_task(payload: TaskIn, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _ = user
    command_bus = CommandBus(db)
    try:
        result = command_bus.dispatch(method="tasks.create", params=payload.model_dump(), user_claims=user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    task = db.get(Task, UUID(result["task_id"]))
    if not task:
        raise HTTPException(status_code=500, detail="Task was created but cannot be loaded")
    return task


@router.post("/{task_id}/retry", response_model=TaskOut)
def retry_task(task_id: UUID, db: Session = Depends(get_db), user_claims: dict = Depends(get_current_user)):
    command_bus = CommandBus(db)
    try:
        command_bus.dispatch(
            method="tasks.retry",
            params={"task_id": str(task_id)},
            user_claims=user_claims,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found after retry")
    return task
