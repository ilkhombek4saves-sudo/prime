"""
CronService — DB-backed scheduled jobs using APScheduler.

Jobs are stored in the `cron_jobs` table and scheduled via AsyncIOScheduler.
When a job fires it dispatches to AgentRunner in a thread executor.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_scheduler = None  # APScheduler AsyncIOScheduler instance


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            _scheduler = AsyncIOScheduler(timezone="UTC")
        except ImportError:
            logger.warning("apscheduler not installed — cron disabled")
    return _scheduler


class CronService:
    """Manage persistent cron jobs."""

    @staticmethod
    async def start() -> None:
        """Load active jobs from DB and start scheduler."""
        scheduler = _get_scheduler()
        if scheduler is None or scheduler.running:
            return

        scheduler.start()
        logger.info("CronService scheduler started")

        # Load existing active jobs
        try:
            jobs = await CronService.list_jobs()
            for job in jobs:
                if job.get("active"):
                    CronService._schedule_job(job)
        except Exception as exc:
            logger.warning("Could not load cron jobs from DB: %s", exc)

    @staticmethod
    async def stop() -> None:
        """Shut down scheduler."""
        scheduler = _get_scheduler()
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("CronService scheduler stopped")

    @staticmethod
    async def add_job(
        name: str,
        schedule: str,
        message: str,
        agent_id: str | None = None,
        session_key: str | None = None,
    ) -> dict:
        """Create a cron job in DB and schedule it."""
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import CronJob

        job_id = uuid.uuid4()
        with SyncSessionLocal() as db:
            job = CronJob(
                id=job_id,
                name=name,
                schedule=schedule,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                message=message,
                session_key=session_key,
                active=True,
            )
            db.add(job)
            db.commit()

        job_dict = {
            "id": str(job_id),
            "name": name,
            "schedule": schedule,
            "message": message,
            "agent_id": agent_id,
            "session_key": session_key,
            "active": True,
            "last_run": None,
            "next_run": None,
        }
        CronService._schedule_job(job_dict)
        logger.info("Cron job added: %s [%s]", name, schedule)
        return job_dict

    @staticmethod
    async def remove_job(job_id: str) -> bool:
        """Delete a cron job from DB and unschedule it."""
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import CronJob

        scheduler = _get_scheduler()
        if scheduler:
            try:
                scheduler.remove_job(f"cron_{job_id}")
            except Exception:
                pass

        with SyncSessionLocal() as db:
            job = db.get(CronJob, uuid.UUID(job_id))
            if job:
                db.delete(job)
                db.commit()
                return True
        return False

    @staticmethod
    async def pause_job(job_id: str) -> bool:
        return await CronService._set_active(job_id, False)

    @staticmethod
    async def resume_job(job_id: str) -> bool:
        return await CronService._set_active(job_id, True)

    @staticmethod
    async def list_jobs() -> list[dict]:
        """Return all cron jobs from DB."""
        try:
            from app.persistence.database import SyncSessionLocal
            from app.persistence.models import CronJob
            from sqlalchemy import select

            with SyncSessionLocal() as db:
                result = db.execute(
                    select(CronJob).order_by(CronJob.created_at.desc())
                )
                return [
                    {
                        "id": str(j.id),
                        "name": j.name,
                        "schedule": j.schedule,
                        "message": j.message,
                        "agent_id": str(j.agent_id) if j.agent_id else None,
                        "session_key": j.session_key,
                        "active": j.active,
                        "last_run": j.last_run.isoformat() if j.last_run else None,
                        "next_run": j.next_run.isoformat() if j.next_run else None,
                    }
                    for j in result.scalars().all()
                ]
        except Exception as exc:
            logger.warning("list_jobs DB error: %s", exc)
            return []

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _schedule_job(job: dict) -> None:
        """Add a job to the APScheduler using its cron expression."""
        scheduler = _get_scheduler()
        if scheduler is None:
            return

        job_id = f"cron_{job['id']}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

        schedule = job["schedule"]
        try:
            parts = schedule.strip().split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                scheduler.add_job(
                    CronService._execute_job,
                    "cron",
                    id=job_id,
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                    args=[job["id"]],
                    replace_existing=True,
                )
            else:
                logger.warning("Unsupported cron schedule format: %s", schedule)
        except Exception as exc:
            logger.error("Failed to schedule cron job %s: %s", job["id"], exc)

    @staticmethod
    async def _execute_job(job_id: str) -> None:
        """Fire a cron job — run agent with the job's message."""
        import asyncio

        logger.info("Executing cron job %s", job_id)
        try:
            from app.persistence.database import SyncSessionLocal
            from app.persistence.models import CronJob, Agent, Provider
            from sqlalchemy import select

            message = ""
            provider_type: Any = "OpenAI"
            provider_config: dict = {}
            workspace_path: str | None = None
            system: str | None = None

            with SyncSessionLocal() as db:
                job = db.get(CronJob, uuid.UUID(job_id))
                if not job or not job.active:
                    return

                message = job.message
                agent_id = job.agent_id

                if agent_id:
                    agent = db.get(Agent, agent_id)
                    if agent:
                        workspace_path = agent.workspace_path
                        system = agent.system_prompt
                        if agent.default_provider_id:
                            prov = db.get(Provider, agent.default_provider_id)
                            if prov:
                                provider_type = prov.type
                                provider_config = prov.config or {}

                job.last_run = datetime.now(timezone.utc)
                db.commit()

            from app.services.agent_runner import AgentRunner
            runner = AgentRunner()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: runner.run(
                    message,
                    provider_type=provider_type,
                    provider_name="cron",
                    provider_config=provider_config,
                    system=system,
                    workspace_path=workspace_path,
                ),
            )

        except Exception as exc:
            logger.error("Cron job %s execution error: %s", job_id, exc, exc_info=True)

    @staticmethod
    async def _set_active(job_id: str, active: bool) -> bool:
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import CronJob

        with SyncSessionLocal() as db:
            job = db.get(CronJob, uuid.UUID(job_id))
            if not job:
                return False
            job.active = active
            db.commit()

        scheduler = _get_scheduler()
        if scheduler:
            apscheduler_id = f"cron_{job_id}"
            try:
                if active:
                    scheduler.resume_job(apscheduler_id)
                else:
                    scheduler.pause_job(apscheduler_id)
            except Exception:
                pass
        return True
