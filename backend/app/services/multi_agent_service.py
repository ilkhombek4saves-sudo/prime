"""
MultiAgentService — spawn, communicate with, and list sub-agents.

Sub-agents run as asyncio background tasks. Results are published to the
parent session inbox so the parent can pick them up.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# In-memory registry of active child tasks: session_key → asyncio.Task
_active_tasks: dict[str, asyncio.Task] = {}
# Inbox for sessions_send: session_key → list of pending messages
_inboxes: dict[str, list[str]] = {}


class MultiAgentService:
    """Manage spawning and communication for sub-agents."""

    # ── Spawn ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def spawn_agent(
        task: str,
        agent_id: str | None = None,
        parent_session_id: str | None = None,
    ) -> str:
        """
        Spawn a sub-agent in the background.
        Returns the child session_key that the caller can poll.
        """
        child_key = f"child-{uuid.uuid4().hex[:8]}"
        _inboxes[child_key] = []

        async def _runner() -> None:
            try:
                logger.info(
                    "Sub-agent %s started (parent=%s, agent_id=%s)",
                    child_key, parent_session_id, agent_id,
                )
                from app.services.agent_runner import AgentRunner
                from app.persistence.database import SyncSessionLocal
                from app.persistence.models import Agent, Provider
                from sqlalchemy import select

                runner = AgentRunner()
                provider_type: Any = "OpenAI"
                provider_config: dict = {}
                workspace_path: str | None = None
                system: str | None = None

                if agent_id:
                    try:
                        with SyncSessionLocal() as db:
                            agent = db.get(Agent, uuid.UUID(agent_id))
                            if agent:
                                workspace_path = agent.workspace_path
                                system = agent.system_prompt
                                if agent.default_provider_id:
                                    prov = db.get(Provider, agent.default_provider_id)
                                    if prov:
                                        provider_type = prov.type
                                        provider_config = prov.config or {}
                    except Exception as exc:
                        logger.warning("Could not load agent config for spawn: %s", exc)

                loop = asyncio.get_event_loop()
                result_text = await loop.run_in_executor(
                    None,
                    lambda: runner.run(
                        task,
                        provider_type=provider_type,
                        provider_name="spawned",
                        provider_config=provider_config,
                        system=system,
                        workspace_path=workspace_path,
                    ),
                )
                _inboxes.setdefault(parent_session_id or "root", []).append(
                    f"[Sub-agent {child_key} completed]: {result_text[:500]}"
                )
                logger.info("Sub-agent %s finished", child_key)
            except Exception as exc:
                logger.error("Sub-agent %s error: %s", child_key, exc, exc_info=True)
                _inboxes.setdefault(parent_session_id or "root", []).append(
                    f"[Sub-agent {child_key} failed]: {exc}"
                )
            finally:
                _active_tasks.pop(child_key, None)

        loop = asyncio.get_event_loop()
        task_obj = loop.create_task(_runner())
        _active_tasks[child_key] = task_obj
        return child_key

    # ── Send ───────────────────────────────────────────────────────────────────

    @staticmethod
    async def send_to_session(session_key: str, message: str) -> str:
        """Deliver a message to a session's inbox."""
        _inboxes.setdefault(session_key, []).append(message)
        return f"Message delivered to session {session_key}"

    # ── List ───────────────────────────────────────────────────────────────────

    @staticmethod
    async def list_sessions(
        limit: int = 20,
        active_minutes: int | None = None,
    ) -> list[dict]:
        """Return in-memory active sub-agent sessions plus DB sessions."""
        sessions = []

        # In-memory tasks
        for key, t in list(_active_tasks.items()):
            sessions.append({
                "session_key": key,
                "status": "active" if not t.done() else "finished",
                "type": "sub-agent",
            })

        # DB sessions (best-effort)
        try:
            from app.persistence.database import SyncSessionLocal
            from app.persistence.models import Session as SessionModel, SessionStatus
            from sqlalchemy import select

            with SyncSessionLocal() as db:
                q = select(SessionModel).where(
                    SessionModel.status == SessionStatus.active
                ).order_by(SessionModel.updated_at.desc()).limit(limit)
                result = db.execute(q)
                for s in result.scalars().all():
                    sessions.append({
                        "session_key": str(s.id),
                        "status": s.status.value,
                        "created_at": s.created_at.isoformat(),
                        "type": "db-session",
                    })
        except Exception as exc:
            logger.debug("DB sessions query failed: %s", exc)

        return sessions[:limit]

    # ── Transcript ─────────────────────────────────────────────────────────────

    @staticmethod
    async def get_transcript(session_key: str) -> list[dict]:
        """Return messages for a session from the DB."""
        try:
            from app.persistence.database import SyncSessionLocal
            from app.persistence.models import Message
            from sqlalchemy import select

            with SyncSessionLocal() as db:
                q = select(Message).where(
                    Message.session_id == uuid.UUID(session_key)
                ).order_by(Message.created_at.asc())
                result = db.execute(q)
                return [
                    {
                        "role": m.role.value,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in result.scalars().all()
                ]
        except Exception as exc:
            logger.warning("Transcript query failed: %s", exc)
            return []

    # ── Inbox ──────────────────────────────────────────────────────────────────

    @staticmethod
    def drain_inbox(session_key: str) -> list[str]:
        """Pop and return all pending messages for a session."""
        return _inboxes.pop(session_key, [])
