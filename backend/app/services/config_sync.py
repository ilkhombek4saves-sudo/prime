from __future__ import annotations

import logging
import os
import uuid
from typing import Iterable

from app.config.settings import get_settings
from app.persistence.database import SessionLocal
from app.persistence.models import (
    Agent,
    Binding,
    Bot,
    DMPolicy,
    Organization,
    Provider,
    ProviderType,
    User,
    UserRole,
)
from app.services.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

_PREFERRED_PROVIDERS = [
    "openai_default",
    "anthropic_default",
    "deepseek_default",
    "kimi_default",
    "glm_default",
    "ollama_default",
]


def _select_default_provider_id(providers: Iterable[Provider]) -> uuid.UUID | None:
    provider_map = {p.name: p for p in providers if p.active}

    for name in _PREFERRED_PROVIDERS:
        p = provider_map.get(name)
        if not p:
            continue
        # Local Ollama doesn't require an API key.
        if p.type == ProviderType.Ollama:
            return p.id
        api_key = (p.config or {}).get("api_key")
        if api_key:
            return p.id

    for p in providers:
        if p.active and (p.config or {}).get("api_key"):
            return p.id

    # Keyless local providers (Ollama) should still be eligible as a default.
    for p in providers:
        if p.active and p.type == ProviderType.Ollama:
            return p.id

    for p in providers:
        if p.active:
            return p.id

    return None


def _ensure_default_org(db) -> Organization:
    org = db.query(Organization).filter(Organization.slug == "default").first()
    if not org:
        org = Organization(name="Prime", slug="default", active=True)
        db.add(org)
        db.commit()
        db.refresh(org)
        logger.info("Created default organization: %s", org.name)
    return org


def _ensure_admin_user(db, org: Organization) -> User:
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if admin:
        if not admin.org_id:
            admin.org_id = org.id
            db.commit()
        return admin

    admin = User(
        username="admin",
        role=UserRole.admin,
        org_id=org.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Created default admin user")
    return admin


def _assign_org(db, org: Organization) -> None:
    for model_cls in (Bot, Agent, Provider):
        db.query(model_cls).filter(model_cls.org_id.is_(None)).update(
            {"org_id": org.id}, synchronize_session="fetch"
        )
    db.query(User).filter(User.org_id.is_(None)).update(
        {"org_id": org.id}, synchronize_session="fetch"
    )
    db.commit()


def sync_config_to_db() -> None:
    """Best-effort sync from config/*.yaml into DB records.

    Auto-provisions: Organization, Providers, Bots, default Agent, Bindings, admin User.
    """
    loader = ConfigLoader()
    loaded = loader.load_and_validate()
    bots_cfg = loaded.get("bots", {}).get("bots", [])
    providers_cfg = loaded.get("providers", {}).get("providers", [])

    settings = get_settings()
    env_tokens = [t.strip() for t in settings.telegram_bot_tokens.split(",") if t.strip()]

    with SessionLocal() as db:
        # Organization
        org = _ensure_default_org(db)

        # Providers
        for pcfg in providers_cfg:
            name = pcfg.get("name")
            if not name:
                continue
            type_str = pcfg.get("type")
            try:
                ptype = ProviderType[type_str]
            except Exception:
                logger.warning("Unknown provider type in config: %s", type_str)
                continue

            provider = db.query(Provider).filter(Provider.name == name).first()
            if not provider:
                provider = Provider(
                    name=name,
                    type=ptype,
                    config=pcfg,
                    active=bool(pcfg.get("active", True)),
                    org_id=org.id,
                )
                db.add(provider)
            else:
                provider.type = ptype
                provider.config = pcfg
                provider.active = bool(pcfg.get("active", True))
                if not provider.org_id:
                    provider.org_id = org.id

        db.commit()

        # Bots (from config)
        created_bots: list[Bot] = []
        for bcfg in bots_cfg:
            token = bcfg.get("token")
            token_env = bcfg.get("token_env")
            if not token and token_env:
                token = os.getenv(token_env, "")
            token = (token or "").strip()
            if not token:
                continue

            bot = db.query(Bot).filter(Bot.token == token).first()
            if not bot:
                bot = Bot(
                    name=bcfg.get("name") or "telegram_bot",
                    token=token,
                    channels=bcfg.get("channels") or ["telegram"],
                    allowed_user_ids=bcfg.get("allowed_user_ids") or [],
                    active=bool(bcfg.get("active", True)),
                    provider_defaults=bcfg.get("provider_defaults") or {},
                    org_id=org.id,
                )
                db.add(bot)
                db.commit()
                db.refresh(bot)
            else:
                bot.name = bcfg.get("name") or bot.name
                bot.channels = bcfg.get("channels") or bot.channels
                bot.allowed_user_ids = bcfg.get("allowed_user_ids") or bot.allowed_user_ids
                bot.active = bool(bcfg.get("active", True))
                bot.provider_defaults = bcfg.get("provider_defaults") or bot.provider_defaults
                if not bot.org_id:
                    bot.org_id = org.id
                db.commit()

            created_bots.append(bot)

        # Fallback bot(s) from TELEGRAM_BOT_TOKENS
        if not created_bots and env_tokens:
            for idx, token in enumerate(env_tokens, start=1):
                bot = db.query(Bot).filter(Bot.token == token).first()
                if not bot:
                    bot = Bot(
                        name=f"telegram_{idx}",
                        token=token,
                        channels=["telegram"],
                        active=True,
                        org_id=org.id,
                    )
                    db.add(bot)
                    db.commit()
                    db.refresh(bot)
                created_bots.append(bot)

        # Default agent + binding if none exists
        providers = db.query(Provider).all()
        default_provider_id = _select_default_provider_id(providers)

        agent = db.query(Agent).filter(Agent.name == "default_agent").first()
        if not agent:
            agent = Agent(
                name="default_agent",
                description="Default Telegram agent",
                default_provider_id=default_provider_id,
                dm_policy=DMPolicy.open,
                memory_enabled=True,
                web_search_enabled=False,
                code_execution_enabled=False,
                system_prompt="You are a helpful assistant.",
                active=True,
                org_id=org.id,
            )
            db.add(agent)
            db.commit()
            db.refresh(agent)
        else:
            if default_provider_id and agent.default_provider_id != default_provider_id:
                agent.default_provider_id = default_provider_id
            if not agent.org_id:
                agent.org_id = org.id
            db.commit()

        for bot in created_bots:
            binding = (
                db.query(Binding)
                .filter(
                    Binding.channel == "telegram",
                    Binding.bot_id == bot.id,
                    Binding.agent_id == agent.id,
                    Binding.active.is_(True),
                )
                .first()
            )
            if not binding:
                binding = Binding(
                    channel="telegram",
                    bot_id=bot.id,
                    agent_id=agent.id,
                    account_id=str(bot.id),
                    peer=None,
                    priority=100,
                    active=True,
                )
                db.add(binding)
                db.commit()

        # Ensure admin user exists and linked to org
        _ensure_admin_user(db, org)

        # Assign org_id to any orphaned resources
        _assign_org(db, org)

        logger.info(
            "Config sync complete: org=%s, %d providers, %d bots",
            org.slug,
            len(providers),
            len(created_bots),
        )
