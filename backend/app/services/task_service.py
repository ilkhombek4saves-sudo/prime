from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistence.models import Plugin, Provider, Task, TaskStatus, User
from app.plugins.registry import build_plugin
from app.providers.registry import build_provider
from app.services.event_bus import get_event_bus


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.event_bus = get_event_bus()

    def execute_task(self, task_id: UUID, user: User) -> Task:
        task = self.db.get(Task, task_id)
        if not task:
            raise ValueError("Task not found")

        provider = self.db.get(Provider, task.provider_id)
        plugin_entity = self.db.get(Plugin, task.plugin_id)
        if not provider or not plugin_entity:
            raise ValueError("Provider or Plugin not found")

        runtime_provider = build_provider(provider.type, provider.name, provider.config)
        runtime_plugin = build_plugin(plugin_entity.name, runtime_provider)

        runtime_plugin.check_permissions(user.role.value)

        task.status = TaskStatus.in_progress
        task.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.event_bus.publish_nowait(
            event_name="task.status",
            data={"task_id": str(task.id), "status": task.status.value},
        )

        try:
            result = runtime_plugin.run(task.input_data)
            task.status = TaskStatus.success
            task.output_data = result
            task.error_message = None
        except Exception as exc:  # pragma: no cover
            task.status = TaskStatus.failed
            task.error_message = str(exc)

        task.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(task)
        self.event_bus.publish_nowait(
            event_name="task.status",
            data={"task_id": str(task.id), "status": task.status.value},
        )
        return task
