"""
Base gateway adapter — abstract class with common helpers for all channel gateways.

Subclasses: TelegramGateway, DiscordGateway, SlackGateway, WhatsAppGateway, WebChatGateway
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.persistence.models import (
    Agent, Bot, Provider, Session, SessionStatus, User, UserRole,
)
from app.services.binding_resolver import BindingResolver
from app.services.dm_policy import DMPolicyService
from app.services.event_bus import get_event_bus
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


@dataclass
class ResolvedContext:
    """Result of resolving a gateway message to an agent context."""
    bot: Bot
    agent: Agent
    provider: Provider
    user: User
    session: Session
    history: list[dict[str, str]]
    system_prompt: str


class GatewayAdapter(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    # ── Common helpers ─────────────────────────────────────────────────────

    @staticmethod
    def resolve_bot(db: DbSession, *, name: str | None = None, token: str | None = None) -> Bot | None:
        """Look up an active bot by name or token."""
        q = db.query(Bot).filter(Bot.active.is_(True))
        if name:
            q = q.filter(Bot.name == name)
        if token:
            q = q.filter(Bot.token == token)
        return q.first()

    @staticmethod
    def resolve_binding(db: DbSession, channel: str, bot: Bot, peer: str | None = None):
        """Resolve a channel binding for the given bot and peer."""
        resolver = BindingResolver(db)
        return resolver.resolve(
            channel=channel,
            account_id=str(bot.id),
            peer=peer,
            bot_id=bot.id,
        )

    @staticmethod
    def check_dm_policy(
        db: DbSession,
        channel: str,
        bot: Bot,
        agent: Agent,
        peer: str,
        sender_user_id: Any,
        *,
        is_group: bool = False,
        bot_mentioned: bool = False,
        device_id: str | None = None,
    ) -> bool:
        """Evaluate DM policy for an incoming message. Returns True if allowed."""
        policy_svc = DMPolicyService(db)
        paired = policy_svc.is_paired(
            channel=channel,
            device_id=device_id,
            account_id=str(bot.id),
            peer=peer,
        )
        decision = policy_svc.evaluate(
            policy=agent.dm_policy,
            sender_user_id=sender_user_id,
            allowed_user_ids=agent.allowed_user_ids,
            paired=paired,
            is_group=is_group,
            bot_mentioned=bot_mentioned,
            group_requires_mention=agent.group_requires_mention,
        )
        return decision.allowed

    @staticmethod
    def get_or_create_user(
        db: DbSession,
        username: str,
        role: UserRole = UserRole.user,
        **extra_fields,
    ) -> User:
        """Find existing user by username or create a new one."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(username=username, role=role, **extra_fields)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def get_or_create_session(
        db: DbSession,
        bot: Bot,
        user: User,
        agent: Agent,
    ) -> Session:
        """Find an active session or create a new one."""
        session = (
            db.query(Session)
            .filter(
                Session.bot_id == bot.id,
                Session.user_id == user.id,
                Session.agent_id == agent.id,
                Session.status == SessionStatus.active,
            )
            .first()
        )
        if not session:
            session = Session(
                bot_id=bot.id,
                user_id=user.id,
                agent_id=agent.id,
                provider_id=agent.default_provider_id,
                status=SessionStatus.active,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        return session

    @staticmethod
    def load_history(
        db: DbSession,
        agent: Agent,
        session: Session,
        memory_svc: MemoryService | None = None,
    ) -> list[dict[str, str]]:
        """Load conversation history if the agent has memory enabled."""
        if not agent.memory_enabled:
            return []
        svc = memory_svc or MemoryService()
        max_msgs = getattr(agent, "max_history_messages", 20)
        return svc.get_history(db, session.id, max_msgs)

    @staticmethod
    def save_and_publish(
        db: DbSession,
        session_id: uuid.UUID,
        user_text: str,
        reply_text: str,
        event_name: str,
        event_data: dict[str, Any],
        memory_svc: MemoryService | None = None,
    ) -> None:
        """Save exchange to memory and publish an event."""
        svc = memory_svc or MemoryService()
        svc.save_exchange(db, session_id, user_text, reply_text)
        get_event_bus().publish_nowait(event_name, event_data)

    @staticmethod
    def resolve_full_context(
        db: DbSession,
        channel: str,
        bot: Bot,
        peer: str,
        sender_username: str,
        sender_user_id: Any,
        *,
        is_group: bool = False,
        bot_mentioned: bool = False,
        device_id: str | None = None,
        memory_svc: MemoryService | None = None,
    ) -> ResolvedContext | None:
        """
        One-call resolution: binding → agent → DM policy → user → session → provider → history.
        Returns None if any step fails (no binding, agent inactive, policy denied, no provider).
        """
        binding = GatewayAdapter.resolve_binding(db, channel, bot, peer)
        if not binding:
            return None

        agent = db.get(Agent, binding.agent_id)
        if not agent or not agent.active:
            return None

        if not GatewayAdapter.check_dm_policy(
            db, channel, bot, agent, peer, sender_user_id,
            is_group=is_group, bot_mentioned=bot_mentioned, device_id=device_id,
        ):
            return None

        user = GatewayAdapter.get_or_create_user(db, sender_username)
        session = GatewayAdapter.get_or_create_session(db, bot, user, agent)

        provider = db.get(Provider, agent.default_provider_id) if agent.default_provider_id else None
        if not provider or not provider.active:
            return None

        history = GatewayAdapter.load_history(db, agent, session, memory_svc)

        return ResolvedContext(
            bot=bot,
            agent=agent,
            provider=provider,
            user=user,
            session=session,
            history=history,
            system_prompt=agent.system_prompt or "",
        )
