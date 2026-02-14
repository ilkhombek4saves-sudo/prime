"""
Cron API — manage scheduled agent jobs.

GET    /api/cron            — list all cron jobs
POST   /api/cron            — create a job
DELETE /api/cron/{id}       — delete a job
POST   /api/cron/{id}/pause
POST   /api/cron/{id}/resume
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.persistence.models import User

router = APIRouter(prefix="/cron", tags=["cron"])


class CronJobCreate(BaseModel):
    name: str
    schedule: str
    message: str
    agent_id: str | None = None
    session_key: str | None = None


class CronJobResponse(BaseModel):
    id: str
    name: str
    schedule: str
    message: str
    agent_id: str | None = None
    session_key: str | None = None
    active: bool
    last_run: str | None = None
    next_run: str | None = None


def _run(coro):
    """Run async coro from sync FastAPI endpoint."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)
        return loop.run_until_complete(coro)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[CronJobResponse])
def list_cron_jobs(current_user: User = Depends(get_current_user)):
    from app.services.cron_service import CronService
    jobs = _run(CronService.list_jobs())
    return [CronJobResponse(**j) for j in jobs]


@router.post("", response_model=CronJobResponse, status_code=201)
def create_cron_job(
    body: CronJobCreate,
    current_user: User = Depends(get_current_user),
):
    from app.services.cron_service import CronService
    job = _run(
        CronService.add_job(
            name=body.name,
            schedule=body.schedule,
            message=body.message,
            agent_id=body.agent_id,
            session_key=body.session_key,
        )
    )
    return CronJobResponse(**job)


@router.delete("/{job_id}", status_code=204)
def delete_cron_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    from app.services.cron_service import CronService
    ok = _run(CronService.remove_job(str(job_id)))
    if not ok:
        raise HTTPException(status_code=404, detail="Cron job not found")


@router.post("/{job_id}/pause", status_code=200)
def pause_cron_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    from app.services.cron_service import CronService
    ok = _run(CronService.pause_job(str(job_id)))
    if not ok:
        raise HTTPException(status_code=404, detail="Cron job not found")
    return {"status": "paused"}


@router.post("/{job_id}/resume", status_code=200)
def resume_cron_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    from app.services.cron_service import CronService
    ok = _run(CronService.resume_job(str(job_id)))
    if not ok:
        raise HTTPException(status_code=404, detail="Cron job not found")
    return {"status": "resumed"}
