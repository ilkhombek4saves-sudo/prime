"""
Background task worker — asyncio loop that executes pending Task rows.

Responsibilities:
  1. Poll tasks table every POLL_INTERVAL seconds for status=pending.
  2. Mark task in_progress, execute via plugin + provider, update result.
  3. Publish task.started / task.completed / task.failed events to event bus.
  4. Also handles pending Document indexing jobs (RAG pipeline).

The worker runs inside the FastAPI lifespan alongside the Telegram gateway.
No external message queue required — designed for single-process deployments.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0      # seconds between polls
MAX_CONCURRENT = 4       # max parallel task executions


class BackgroundWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="background-worker")
        logger.info("Background worker started (poll_interval=%.1fs)", POLL_INTERVAL)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background worker stopped")

    # ── Main loop ─────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception as exc:
                logger.error("Worker loop error: %s", exc, exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self) -> None:
        loop = asyncio.get_running_loop()
        # Run DB polling in thread so it doesn't block the event loop
        pending_task_ids, pending_doc_ids = await loop.run_in_executor(
            None, self._fetch_pending_ids
        )

        for task_id in pending_task_ids:
            asyncio.create_task(self._run_task(task_id))

        for doc_id in pending_doc_ids:
            asyncio.create_task(self._index_document(doc_id))

    # ── Plugin task execution ─────────────────────────────────────────────

    async def _run_task(self, task_id: uuid.UUID) -> None:
        loop = asyncio.get_running_loop()
        async with self._semaphore:
            await loop.run_in_executor(None, self._execute_task, task_id)

    def _execute_task(self, task_id: uuid.UUID) -> None:
        from app.persistence.database import SessionLocal
        from app.persistence.models import Task, TaskStatus
        from app.services.event_bus import get_event_bus

        now = datetime.now(timezone.utc)
        bus = get_event_bus()

        with SessionLocal() as db:
            task: Task | None = db.get(Task, task_id)
            if not task or task.status != TaskStatus.pending:
                return  # Already picked up by another worker instance

            task.status = TaskStatus.in_progress
            task.started_at = now
            db.commit()

        bus.publish_nowait("task.started", {"task_id": str(task_id)})

        try:
            result = self._run_plugin(task_id)
            with SessionLocal() as db:
                task = db.get(Task, task_id)
                if task:
                    task.status = TaskStatus.success
                    task.output_data = result
                    task.finished_at = datetime.now(timezone.utc)
                    db.commit()
            bus.publish_nowait("task.completed", {"task_id": str(task_id), "result": result})
            logger.info("Task %s completed", task_id)

        except Exception as exc:
            logger.error("Task %s failed: %s", task_id, exc, exc_info=True)
            with SessionLocal() as db:
                task = db.get(Task, task_id)
                if task:
                    task.status = TaskStatus.failed
                    task.error_message = str(exc)[:1000]
                    task.finished_at = datetime.now(timezone.utc)
                    db.commit()
            bus.publish_nowait("task.failed", {"task_id": str(task_id), "error": str(exc)})

    def _run_plugin(self, task_id: uuid.UUID) -> dict:
        """Build plugin instance and execute it synchronously."""
        from app.persistence.database import SessionLocal
        from app.persistence.models import Task
        from app.providers.registry import build_provider
        from app.plugins.registry import build_plugin

        with SessionLocal() as db:
            task: Task | None = db.get(Task, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            plugin_record = task.plugin
            provider_record = task.provider
            input_data = dict(task.input_data or {})

        provider = build_provider(
            str(provider_record.type),
            provider_record.name,
            dict(provider_record.config),
        )
        plugin = build_plugin(plugin_record.name, provider)
        return plugin.run(input_data)

    # ── Document indexing ─────────────────────────────────────────────────

    async def _index_document(self, doc_id: uuid.UUID) -> None:
        loop = asyncio.get_running_loop()
        async with self._semaphore:
            await loop.run_in_executor(None, self._index_document_sync, doc_id)

    def _index_document_sync(self, doc_id: uuid.UUID) -> None:
        from app.persistence.database import SessionLocal
        from app.services.rag_service import get_rag_service
        from app.services.event_bus import get_event_bus

        bus = get_event_bus()
        try:
            with SessionLocal() as db:
                get_rag_service().index_document(db, doc_id)
            bus.publish_nowait("document.indexed", {"document_id": str(doc_id)})
        except Exception as exc:
            logger.error("Document indexing failed for %s: %s", doc_id, exc)
            bus.publish_nowait("document.failed", {"document_id": str(doc_id), "error": str(exc)})

    # ── DB polling (runs in thread) ───────────────────────────────────────

    def _fetch_pending_ids(
        self,
    ) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        from app.persistence.database import SessionLocal
        from app.persistence.models import Document, DocumentStatus, Task, TaskStatus

        try:
            with SessionLocal() as db:
                tasks = (
                    db.query(Task.id)
                    .filter(Task.status == TaskStatus.pending)
                    .limit(MAX_CONCURRENT)
                    .all()
                )
                docs = (
                    db.query(Document.id)
                    .filter(Document.status == DocumentStatus.pending)
                    .limit(MAX_CONCURRENT)
                    .all()
                )
                return [r[0] for r in tasks], [r[0] for r in docs]
        except Exception as exc:
            logger.warning("Worker _fetch_pending_ids error: %s", exc)
            return [], []


_worker = BackgroundWorker()


def get_worker() -> BackgroundWorker:
    return _worker
