from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistence.models import Agent, Plugin, Provider, Task, TaskStatus, User
from app.schemas.task import TaskIn
from app.services.binding_resolver import BindingResolver
from app.services.dm_policy import DMPolicyService
from app.services.task_service import TaskService


class CommandBus:
    """Unified command execution path used by both WS protocol and REST routes."""

    def __init__(self, db: Session):
        self.db = db

    def dispatch(self, method: str, params: dict, user_claims: dict) -> dict:
        if method == "health.get":
            return {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if method == "tasks.list":
            tasks = self.db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
            return {
                "items": [
                    {
                        "id": str(task.id),
                        "status": task.status.value,
                        "session_id": str(task.session_id),
                        "plugin_id": str(task.plugin_id),
                        "provider_id": str(task.provider_id),
                    }
                    for task in tasks
                ]
            }

        if method == "tasks.create":
            try:
                payload = TaskIn.model_validate(params)
            except Exception as exc:
                raise ValueError(f"Invalid tasks.create payload: {exc}") from exc
            provider = self.db.get(Provider, payload.provider_id)
            plugin = self.db.query(Plugin).filter(Plugin.name == payload.plugin_name).first()
            if not provider or not plugin:
                raise ValueError("Provider or plugin not found")

            task = Task(
                session_id=payload.session_id,
                plugin_id=plugin.id,
                provider_id=payload.provider_id,
                status=TaskStatus.pending,
                input_data=payload.input_data,
            )
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            return {"task_id": str(task.id), "status": task.status.value}

        if method == "tasks.retry":
            try:
                task_id = UUID(str(params["task_id"]))
            except Exception as exc:
                raise ValueError("Invalid task_id") from exc
            user = self.db.get(User, UUID(str(user_claims["sub"])))
            if not user:
                raise ValueError("User not found")

            service = TaskService(self.db)
            task = service.execute_task(task_id=task_id, user=user)
            return {
                "task_id": str(task.id),
                "status": task.status.value,
                "output_data": task.output_data,
                "error_message": task.error_message,
            }

        if method == "bindings.resolve":
            channel = str(params.get("channel", "")).strip()
            if not channel:
                raise ValueError("channel is required")

            bot_id_raw = params.get("bot_id")
            bot_id = UUID(str(bot_id_raw)) if bot_id_raw else None
            resolver = BindingResolver(self.db)
            match = resolver.resolve(
                channel=channel,
                account_id=params.get("account_id"),
                peer=params.get("peer"),
                bot_id=bot_id,
            )
            if not match:
                return {"matched": False, "reason": "no_matching_binding"}

            return {
                "matched": True,
                "binding_id": str(match.id),
                "agent_id": str(match.agent_id),
                "reason": "matched",
            }

        if method == "policy.dm_check":
            agent_id_raw = params.get("agent_id")
            if not agent_id_raw:
                raise ValueError("agent_id is required")

            try:
                agent_id = UUID(str(agent_id_raw))
            except Exception as exc:
                raise ValueError("Invalid agent_id") from exc

            agent = self.db.get(Agent, agent_id)
            if not agent:
                raise ValueError("Agent not found")

            policy_service = DMPolicyService(self.db)
            paired = policy_service.is_paired(
                channel=str(params.get("channel", "telegram")),
                device_id=params.get("device_id"),
                account_id=params.get("account_id"),
                peer=params.get("peer"),
            )

            sender_user_id = params.get("sender_user_id")
            if sender_user_id is not None:
                try:
                    sender_user_id = int(sender_user_id)
                except Exception as exc:
                    raise ValueError("sender_user_id must be int") from exc

            decision = policy_service.evaluate(
                policy=agent.dm_policy,
                sender_user_id=sender_user_id,
                allowed_user_ids=agent.allowed_user_ids,
                paired=paired,
                is_group=bool(params.get("is_group", False)),
                bot_mentioned=bool(params.get("bot_mentioned", False)),
                group_requires_mention=bool(agent.group_requires_mention),
            )
            return {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "paired": paired,
                "policy": agent.dm_policy.value,
            }

        raise ValueError(f"Unsupported command method: {method}")
