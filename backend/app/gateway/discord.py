"""
Discord gateway adapter — uses discord.py to receive messages,
route through binding resolver + DM policy, and reply via agent runner.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.gateway.base import GatewayAdapter
from app.persistence.database import SessionLocal
from app.persistence.models import (
    Agent, Bot, Provider, Session, SessionStatus, User, UserRole,
)
from app.services.agent_runner import AgentRunner
from app.services.binding_resolver import BindingResolver
from app.services.dm_policy import DMPolicyService
from app.services.event_bus import get_event_bus
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

_memory_svc = MemoryService()
_agent_runner = AgentRunner()

try:
    import discord
    _HAS_DISCORD = True
except ImportError:
    _HAS_DISCORD = False


class DiscordGateway(GatewayAdapter):
    def __init__(self, bot_configs: list[dict]) -> None:
        self._configs = bot_configs
        self._clients: list = []

    async def start(self) -> None:
        if not _HAS_DISCORD:
            logger.warning("discord.py not installed — Discord gateway disabled")
            return
        for cfg in self._configs:
            client = _build_client(cfg)
            self._clients.append(client)
            asyncio.create_task(client.start(cfg["token"]))
        logger.info("Started %d Discord bot(s)", len(self._clients))

    async def stop(self) -> None:
        for client in self._clients:
            try:
                await client.close()
            except Exception:
                pass
        logger.info("Discord gateway stopped")


def _build_client(cfg: dict):
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    bot_name = cfg.get("name", "discord_bot")

    @client.event
    async def on_ready():
        logger.info("Discord bot %s connected as %s", bot_name, client.user)

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        if message.author.bot:
            return

        text = message.content
        if not text:
            return

        sender_id = message.author.id
        channel_id = str(message.channel.id)
        is_dm = isinstance(message.channel, discord.DMChannel)
        bot_mentioned = client.user in message.mentions if not is_dm else True

        with SessionLocal() as db:
            bot_record = db.query(Bot).filter(Bot.name == bot_name, Bot.active.is_(True)).first()
            if not bot_record:
                return

            resolver = BindingResolver(db)
            binding = resolver.resolve(
                channel="discord",
                account_id=str(bot_record.id),
                peer=channel_id,
                bot_id=bot_record.id,
            )
            if not binding:
                return

            agent = db.get(Agent, binding.agent_id)
            if not agent or not agent.active:
                return

            policy_svc = DMPolicyService(db)
            paired = policy_svc.is_paired(
                channel="discord", device_id=None,
                account_id=str(bot_record.id), peer=channel_id,
            )
            decision = policy_svc.evaluate(
                policy=agent.dm_policy,
                sender_user_id=sender_id,
                allowed_user_ids=agent.allowed_user_ids,
                paired=paired,
                is_group=not is_dm,
                bot_mentioned=bot_mentioned,
                group_requires_mention=agent.group_requires_mention,
            )
            if not decision.allowed:
                return

            user = db.query(User).filter(User.username == f"discord_{sender_id}").first()
            if not user:
                user = User(username=f"discord_{sender_id}", role=UserRole.user)
                db.add(user)
                db.commit()
                db.refresh(user)

            session = (
                db.query(Session)
                .filter(
                    Session.bot_id == bot_record.id,
                    Session.user_id == user.id,
                    Session.agent_id == agent.id,
                    Session.status == SessionStatus.active,
                )
                .first()
            )
            if not session:
                session = Session(
                    bot_id=bot_record.id, user_id=user.id,
                    agent_id=agent.id, provider_id=agent.default_provider_id,
                    status=SessionStatus.active,
                )
                db.add(session)
                db.commit()
                db.refresh(session)

            provider = db.get(Provider, agent.default_provider_id) if agent.default_provider_id else None
            if not provider or not provider.active:
                await message.reply("Provider not configured.")
                return

            history = []
            if agent.memory_enabled:
                history = _memory_svc.get_history(db, session.id, agent.max_history_messages)

            provider_type = provider.type
            provider_config = dict(provider.config)
            agent_system_prompt = agent.system_prompt or ""

        loop = asyncio.get_running_loop()
        try:
            async with message.channel.typing():
                result = await loop.run_in_executor(
                    None,
                    lambda: _agent_runner.run(
                        text,
                        provider_type=provider_type,
                        provider_name=provider.name if provider else "unknown",
                        provider_config=provider_config,
                        system=agent_system_prompt or None,
                        history=history,
                    ),
                )
            for chunk in _split_message(result, 2000):
                await message.reply(chunk)
        except Exception as exc:
            logger.error("Discord message error: %s", exc, exc_info=True)
            await message.reply("Error processing request.")

        with SessionLocal() as db:
            _memory_svc.save_exchange(db, session.id, text, result)

        get_event_bus().publish_nowait(
            "task.discord_message",
            {"bot": bot_name, "channel": channel_id, "agent": agent.name if agent else "unknown"},
        )

    return client


def _split_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


def build_discord_gateway(configs: list[dict]) -> DiscordGateway:
    return DiscordGateway(configs)
