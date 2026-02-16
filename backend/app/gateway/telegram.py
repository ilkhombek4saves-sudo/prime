"""
Telegram gateway — wraps python-telegram-bot to receive messages,
route them through the DM policy / binding resolver, call the
configured provider, and send the response back.

Supports per-agent features:
  - memory_enabled       : inject conversation history into every call
  - web_search_enabled   : search DuckDuckGo and inject results as context
  - system_prompt        : custom system instructions for the agent
"""
from __future__ import annotations

import asyncio
import logging
import re
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.gateway.base import GatewayAdapter
from app.persistence.database import SessionLocal
from app.persistence.models import (
    Agent,
    Bot,
    PairingRequest,
    PairingStatus,
    Provider,
    Session,
    SessionStatus,
    User,
    UserRole,
)
from app.services.agent_runner import AgentRunner
from app.services.agent_runner_async import get_agent_runner_async
from app.services.binding_resolver import BindingResolver
from app.services.dm_policy import DMPolicyService
from app.services.event_bus import get_event_bus
from app.services.memory_service import MemoryService
from app.services.session_summary import SessionSummaryService
from app.services.token_optimizer import TokenOptimizationService
from app.services.web_search import WebSearchService
from app.services.long_term_memory import LongTermMemoryService
from app.services.cost_tracker import CostTracker
from app.config.settings import get_settings
from app.services.pairing_service import PairingLimitError, create_request

logger = logging.getLogger(__name__)

_memory_svc = MemoryService()
_summary_svc = SessionSummaryService
_search_svc = WebSearchService()
_agent_runner = AgentRunner()
_token_optimizer = TokenOptimizationService()
_ltm_svc = LongTermMemoryService()
_cost_tracker = CostTracker()

# Feature flags for simplified mode
USE_SUMMARY_INSTEAD_OF_HISTORY = True  # If True, use summary instead of full message history
DISABLE_AUDIT_LOG = True  # If True, skip audit logging

_FALLBACK_PROVIDER_ORDER = [
    "openai_default",
    "deepseek_default",
    "kimi_default",
    "glm_default",
    "ollama_default",
]
_FALLBACK_PROVIDER_TYPES = {
    "OpenAI",
    "Anthropic",
    "DeepSeek",
    "Mistral",
    "Gemini",
    "Kimi",
    "Qwen",
    "GLM",
    "Ollama",
}

_HTTP_STATUS_RE = re.compile(r"\b([45]\d{2})\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_TELEGRAM_TOKEN_RE = re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{20,}\b")


@dataclass(frozen=True)
class _ProviderErrorInfo:
    code: str
    summary: str
    hint: str
    http_status: int | None
    detail: str


def _sanitize_error_detail(raw: str) -> str:
    text = (raw or "").replace("\n", " ").strip()
    if not text:
        text = "unknown error"
    text = _OPENAI_KEY_RE.sub("sk-***", text)
    text = _TELEGRAM_TOKEN_RE.sub("***:***", text)
    if len(text) > 320:
        return text[:320] + "...(truncated)"
    return text


def _extract_http_status(text: str) -> int | None:
    match = _HTTP_STATUS_RE.search(text or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _classify_provider_error(exc: Exception) -> _ProviderErrorInfo:
    detail = _sanitize_error_detail(str(exc))
    low = detail.lower()
    status = _extract_http_status(detail)

    if (
        "api_key is required" in low
        or "invalid api key" in low
        or "invalid_api_key" in low
        or "unauthorized" in low
        or "authentication" in low
        or status == 401
    ):
        return _ProviderErrorInfo(
            code="auth_error",
            summary="Провайдер отклонил ключ доступа.",
            hint="Проверьте API ключ и его привязку к выбранному провайдеру.",
            http_status=status,
            detail=detail,
        )

    if (
        status == 402
        or "insufficient balance" in low
        or "余额不足" in low  # common BigModel/Z.ai billing message
        or "recharge" in low
        or "no resource package" in low
        or "\"code\":\"1113\"" in low
        or "code\":\"1113\"" in low
        or "insufficient credits" in low
        or "insufficient_quota" in low
        or "billing" in low
        or "payment" in low
        or "quota exceeded" in low
    ):
        return _ProviderErrorInfo(
            code="billing_error",
            summary="У провайдера не хватает лимита/баланса.",
            hint="Пополните баланс или переключите агента на другой провайдер.",
            http_status=status,
            detail=detail,
        )

    if status == 429 or "rate limit" in low or "too many requests" in low:
        return _ProviderErrorInfo(
            code="rate_limit",
            summary="Провайдер ограничил частоту запросов.",
            hint="Подождите и повторите запрос или настройте fallback провайдера.",
            http_status=status,
            detail=detail,
        )

    if status == 404 or "model" in low and "not found" in low:
        return _ProviderErrorInfo(
            code="model_not_found",
            summary="Модель или endpoint не найдены.",
            hint="Проверьте `default_model` и `api_base` в конфиге провайдера.",
            http_status=status,
            detail=detail,
        )

    if (
        status in {500, 502, 503, 504}
        or "temporarily unavailable" in low
        or "service unavailable" in low
        or "overloaded" in low
    ):
        return _ProviderErrorInfo(
            code="provider_unavailable",
            summary="Провайдер временно недоступен.",
            hint="Повторите запрос позже или используйте fallback провайдер.",
            http_status=status,
            detail=detail,
        )

    if (
        "request failed" in low
        or "connecterror" in low
        or "timeout" in low
        or "timed out" in low
        or "connection" in low
    ):
        return _ProviderErrorInfo(
            code="network_error",
            summary="Сбой сети при обращении к провайдеру.",
            hint="Проверьте сетевую доступность и `api_base`.",
            http_status=status,
            detail=detail,
        )

    return _ProviderErrorInfo(
        code="provider_error",
        summary="Неизвестная ошибка провайдера.",
        hint="Проверьте логи backend и конфиг выбранного провайдера.",
        http_status=status,
        detail=detail,
    )


def _should_try_fallback(exc: Exception) -> bool:
    code = _classify_provider_error(exc).code
    return code in {
        "auth_error",
        "billing_error",
        "rate_limit",
        "model_not_found",
        "provider_unavailable",
        "network_error",
    }


def _format_provider_error_message(
    *,
    provider_name: str,
    exc: Exception,
    debug: bool,
    error_id: str,
) -> str:
    if not debug:
        return (
            "Временная ошибка при обработке запроса. Попробуйте позже.\n"
            f"Ошибка ID: `{error_id}`"
        )

    info = _classify_provider_error(exc)
    lines = [
        f"Ошибка у провайдера `{provider_name}` ({info.code}).",
        info.summary,
        f"Что сделать: {info.hint}",
        f"Ошибка ID: `{error_id}`",
    ]
    if info.http_status:
        lines.insert(2, f"HTTP: `{info.http_status}`")
    lines.append(f"Детали: {info.detail}")
    return "\n".join(lines)


def _format_internal_error_message(exc: Exception, *, debug: bool, error_id: str) -> str:
    detail = _sanitize_error_detail(str(exc))
    if debug:
        return f"Ошибка обработки сообщения (id: `{error_id}`): {detail}"
    return (
        f"Ошибка обработки сообщения (id: `{error_id}`). "
        "Проверьте /status и логи backend."
    )


def _format_command_help() -> str:
    return (
        "Доступные команды:\n"
        "/start — краткий статус и как работать\n"
        "/help — список команд\n"
        "/new — начать новый диалог (сбросить сессию)\n"
        "/settings — текущие настройки агента\n"
        "/status — статус маршрутизации и провайдера\n"
        "/whoami — ваш id и статус доступа\n"
        "/pair — запросить привязку (если требуется)\n"
    )


def _get_bot_and_binding(db, msg, token: str):
    bot_record: Bot | None = (
        db.query(Bot).filter(Bot.token == token, Bot.active.is_(True)).first()
    )
    if not bot_record:
        return None, None, None, "unknown_bot"

    resolver = BindingResolver(db)
    binding = resolver.resolve(
        channel="telegram",
        account_id=str(bot_record.id),
        peer=str(msg.chat.id),
        bot_id=bot_record.id,
    )
    if not binding:
        return bot_record, None, None, "no_binding"

    agent: Agent | None = db.get(Agent, binding.agent_id)
    if not agent or not agent.active:
        return bot_record, binding, None, "no_agent"

    return bot_record, binding, agent, None


def _get_or_create_user(db, msg) -> User | None:
    sender_id = msg.from_user.id if msg.from_user else None
    if sender_id is None:
        return None
    user = db.query(User).filter(User.telegram_id == sender_id).first()
    if user:
        return user
    user = User(
        telegram_id=sender_id,
        username=msg.from_user.username or f"tg_{sender_id}",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_active_session(db, bot_id, user_id, agent_id) -> Session | None:
    return (
        db.query(Session)
        .filter(
            Session.bot_id == bot_id,
            Session.user_id == user_id,
            Session.agent_id == agent_id,
            Session.status == SessionStatus.active,
        )
        .first()
    )


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        if err == "no_binding":
            await msg.reply_text(
                "Бот ещё не привязан к агенту. Админ: создайте binding в админке."
            )
            return
        if err == "no_agent":
            await msg.reply_text("Агент для этого канала не найден или отключен.")
            return

        policy_svc = DMPolicyService(db)
        paired = policy_svc.is_paired(
            channel="telegram",
            device_id=None,
            account_id=str(bot_record.id),
            peer=str(msg.chat.id),
        )
        decision = policy_svc.evaluate(
            policy=agent.dm_policy,
            sender_user_id=msg.from_user.id if msg.from_user else None,
            allowed_user_ids=agent.allowed_user_ids,
            paired=paired,
            is_group=msg.chat.type in ("group", "supergroup", "channel"),
            bot_mentioned=True,
            group_requires_mention=agent.group_requires_mention,
        )
        if not decision.allowed and decision.reason == "pairing_required":
            await msg.reply_text(
                "Доступ закрыт. Нужна привязка. Отправьте /pair и дождитесь одобрения."
            )
            return

    await msg.reply_text(
        "Prime готов к работе. Пишите сообщение боту.\n\n" + _format_command_help()
    )


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    await msg.reply_text(_format_command_help())


async def _cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        if err == "no_binding":
            await msg.reply_text("Нет binding для этого чата. Админ: настройте binding.")
            return
        if err == "no_agent":
            await msg.reply_text("Агент для этого канала не найден или отключен.")
            return
        user = _get_or_create_user(db, msg)
        if not user:
            await msg.reply_text("Не удалось определить пользователя.")
            return
        session = _get_active_session(db, bot_record.id, user.id, agent.id)
        if session:
            session.status = SessionStatus.finished
            # Clear summary when resetting session
            if USE_SUMMARY_INSTEAD_OF_HISTORY:
                try:
                    _summary_svc(db).clear_summary(session)
                except Exception:
                    pass
            db.commit()
    await msg.reply_text("Сессия сброшена. Начните новый диалог.")


async def _cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        if err == "no_binding":
            await msg.reply_text("Нет binding для этого чата. Админ: настройте binding.")
            return
        if err == "no_agent":
            await msg.reply_text("Агент для этого канала не найден или отключен.")
            return

        provider_id = agent.default_provider_id
        provider = db.get(Provider, provider_id) if provider_id else None
        provider_name = provider.name if provider else "не задан"
        provider_type = provider.type.value if provider else "n/a"

    await msg.reply_text(
        "Текущие настройки:\n"
        f"Агент: {agent.name}\n"
        f"DM политика: {agent.dm_policy}\n"
        f"Память: {'on' if agent.memory_enabled else 'off'}\n"
        f"Web search: {'on' if agent.web_search_enabled else 'off'}\n"
        f"Code exec: {'on' if agent.code_execution_enabled else 'off'}\n"
        f"Провайдер: {provider_name} ({provider_type})"
    )


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        if err == "no_binding":
            await msg.reply_text("Нет binding для этого чата. Админ: настройте binding.")
            return
        if err == "no_agent":
            await msg.reply_text("Агент для этого канала не найден или отключен.")
            return
        provider_id = agent.default_provider_id
        provider = db.get(Provider, provider_id) if provider_id else None
        provider_state = "ok" if provider and provider.active else "disabled"
        paired = DMPolicyService(db).is_paired(
            channel="telegram",
            device_id=None,
            account_id=str(bot_record.id),
            peer=str(msg.chat.id),
        )

    await msg.reply_text(
        "Статус:\n"
        f"Gateway: ok\n"
        f"Агент: {agent.name}\n"
        f"Провайдер: {provider.name if provider else 'не задан'} ({provider_state})\n"
        f"Pairing: {'paired' if paired else 'not paired'}"
    )


async def _cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, _agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        user = _get_or_create_user(db, msg)
        paired = DMPolicyService(db).is_paired(
            channel="telegram",
            device_id=None,
            account_id=str(bot_record.id),
            peer=str(msg.chat.id),
        ) if bot_record else False

    sender = msg.from_user
    username = f"@{sender.username}" if sender and sender.username else "—"
    await msg.reply_text(
        "Ваш профиль:\n"
        f"id: {sender.id if sender else 'unknown'}\n"
        f"username: {username}\n"
        f"paired: {'yes' if paired else 'no'}"
    )


async def _cmd_pair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    with SessionLocal() as db:
        bot_record, _binding, _agent, err = _get_bot_and_binding(db, msg, context.bot.token)
        if err == "unknown_bot":
            await msg.reply_text("Бот не найден или отключен.")
            return
        if not bot_record:
            await msg.reply_text("Бот не найден или отключен.")
            return

        device_id = f"tg:{bot_record.id}:{msg.chat.id}"
        try:
            request = create_request(
                db,
                device_id=device_id,
                channel="telegram",
                account_id=str(bot_record.id),
                peer=str(msg.chat.id),
                requested_by_user_id=msg.from_user.id if msg.from_user else None,
                request_meta={
                    "username": msg.from_user.username if msg.from_user else None,
                    "chat_title": msg.chat.title if msg.chat else None,
                },
                expires_in_minutes=30,
            )
        except PairingLimitError as exc:
            await msg.reply_text(f"Нельзя создать запрос: {exc}")
            return

    await msg.reply_text(
        "Запрос на привязку создан.\n"
        f"Код: {request.code}\n"
        "Передайте код администратору для подтверждения."
    )


async def _typing_loop(bot, chat_id: int, stop: asyncio.Event) -> None:
    """Send 'typing' action every 4 s until stop is set (Telegram clears it after ~5 s)."""
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


class _StreamBuffer:
    """
    Accumulates tokens from a background thread and lets the asyncio event loop
    flush them to a Telegram message edit every FLUSH_INTERVAL seconds.

    Telegram rate limit: ~20 edits/min per chat → flush every ~0.5 s is safe.
    """
    FLUSH_INTERVAL = 0.5  # seconds between message edits

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._parts: list[str] = []
        self._lock = asyncio.Lock()

    def push(self, token: str) -> None:
        """Called from the provider thread — thread-safe append."""
        self._loop.call_soon_threadsafe(self._parts.append, token)

    def get_text(self) -> str:
        return "".join(self._parts)


async def _stream_to_telegram(
    bot,
    chat_id: int,
    buffer: _StreamBuffer,
    stop: asyncio.Event,
) -> int | None:
    """
    Sends an initial placeholder, then edits it with accumulated tokens
    every FLUSH_INTERVAL seconds until stop is set, then does a final edit.
    Returns the sent message_id (for callers that need it).
    """
    try:
        sent = await bot.send_message(chat_id=chat_id, text="▍")
    except Exception:
        return None

    msg_id = sent.message_id
    last_text = ""

    while not stop.is_set():
        await asyncio.sleep(_StreamBuffer.FLUSH_INTERVAL)
        current = buffer.get_text()
        if current and current != last_text:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=current + " ▍",  # cursor indicator
                )
                last_text = current
            except Exception:
                pass

    # Final edit — full text, no cursor
    final = buffer.get_text()
    if final and final != last_text:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=final,
            )
        except Exception:
            pass
    return msg_id


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("PTB unhandled exception: %s", context.error, exc_info=context.error)


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core message handler shared by all Telegram bots."""
    try:
        await _handle_message_inner(update, context)
    except Exception as exc:
        error_id = uuid.uuid4().hex[:8]
        # Детальное логирование с полным стектрейсом
        logger.error(
            "TELEGRAM_HANDLER_ERROR id=%s error_type=%s error=%s\nFull traceback:\n%s",
            error_id,
            type(exc).__name__,
            str(exc),
            traceback.format_exc()
        )
        if update.message:
            settings = get_settings()
            show_debug = settings.telegram_show_errors or settings.app_env != "prod"
            error_msg = _format_internal_error_message(exc, debug=show_debug, error_id=error_id)
            logger.error("Sending error message to user: %s", error_msg)
            await update.message.reply_text(error_msg)


async def _handle_message_inner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    me = await context.bot.get_me()
    bot_username = me.username or ""
    sender_id = msg.from_user.id if msg.from_user else None
    is_group = msg.chat.type in ("group", "supergroup", "channel")
    bot_mentioned = f"@{bot_username}" in (msg.text or "") if is_group else True

    # ── DB phase: resolve everything we need, then close the session ──────────
    with SessionLocal() as db:
        token = context.bot.token
        bot_record: Bot | None = (
            db.query(Bot).filter(Bot.token == token, Bot.active.is_(True)).first()
        )
        if not bot_record:
            logger.warning("Received message for unknown/inactive bot token")
            return

        channel = "telegram"
        account_id = str(bot_record.id)
        peer = str(msg.chat.id)

        resolver = BindingResolver(db)
        binding = resolver.resolve(
            channel=channel,
            account_id=account_id,
            peer=peer,
            bot_id=bot_record.id,
        )
        if not binding:
            logger.debug("No binding found for chat %s", msg.chat.id)
            return

        agent: Agent | None = db.get(Agent, binding.agent_id)
        if not agent or not agent.active:
            return

        # DM policy
        policy_svc = DMPolicyService(db)
        paired = policy_svc.is_paired(
            channel=channel,
            device_id=None,
            account_id=account_id,
            peer=peer,
        )
        decision = policy_svc.evaluate(
            policy=agent.dm_policy,
            sender_user_id=sender_id,
            allowed_user_ids=agent.allowed_user_ids,
            paired=paired,
            is_group=is_group,
            bot_mentioned=bot_mentioned,
            group_requires_mention=agent.group_requires_mention,
        )
        if not decision.allowed:
            logger.debug("DM policy denied: reason=%s chat=%s", decision.reason, msg.chat.id)
            return

        # Find or create User
        user: User | None = None
        if sender_id is not None:
            user = db.query(User).filter(User.telegram_id == sender_id).first()
            if not user:
                user = User(
                    telegram_id=sender_id,
                    username=msg.from_user.username or f"tg_{sender_id}",
                    role=UserRole.user,
                )
                db.add(user)
                db.commit()
                db.refresh(user)

        # Find or create Session
        session: Session | None = None
        if user:
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
            if session and agent.default_provider_id and session.provider_id != agent.default_provider_id:
                session.provider_id = agent.default_provider_id
                db.commit()
        if not session and user:
            session = Session(
                bot_id=bot_record.id,
                user_id=user.id,
                agent_id=agent.id,
                provider_id=agent.default_provider_id,
                status=SessionStatus.active,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        # Resolve provider
        provider_id = (session.provider_id if session else None) or agent.default_provider_id
        if not provider_id:
            await msg.reply_text(
                "Для этого агента не настроен провайдер. "
                "Админ: задайте default provider в настройках."
            )
            return

        provider_record: Provider | None = db.get(Provider, provider_id)
        if not provider_record or not provider_record.active:
            await msg.reply_text(
                "Выбранный провайдер недоступен или отключен. "
                "Проверьте настройки провайдера в админке."
            )
            return

        # Load fallback providers in case of auth/billing errors.
        providers_all = db.query(Provider).filter(Provider.active.is_(True)).all()
        provider_candidates: list[Provider] = []
        name_rank = {name: idx for idx, name in enumerate(_FALLBACK_PROVIDER_ORDER)}
        for p in providers_all:
            ptype = str(getattr(p.type, "value", p.type))
            if ptype not in _FALLBACK_PROVIDER_TYPES:
                continue
            # Local Ollama can run without any key.
            if ptype != "Ollama" and not (p.config or {}).get("api_key"):
                continue
            provider_candidates.append(p)

        provider_candidates.sort(
            key=lambda p: (name_rank.get(p.name, 999), p.name)
        )

        provider_type = provider_record.type
        provider_name = provider_record.name
        provider_config = dict(provider_record.config)

        # Capture agent settings (before DB session closes)
        session_id = session.id if session else None
        agent_id = agent.id
        agent_system_prompt = agent.system_prompt or ""
        agent_web_search = agent.web_search_enabled
        agent_memory = agent.memory_enabled
        agent_max_history = agent.max_history_messages
        agent_name = agent.name
        agent_code_exec = agent.code_execution_enabled
        agent_workspace = agent.workspace_path  # may be None

        # Load conversation context (summary or full history)
        history: list[dict] = []
        session_summary = ""
        if agent_memory and session_id:
            if USE_SUMMARY_INSTEAD_OF_HISTORY:
                # Use lightweight summary instead of full message history
                session_summary = _summary_svc(db).get_summary(session)
            else:
                # Use full message history (legacy mode)
                history = _memory_svc.get_history(db, session_id, agent_max_history)

        # Long-term memory: recall cross-session facts about this user
        ltm_context = ""
        if user:
            try:
                memories = _ltm_svc.recall(db, user.id, agent_id)
                ltm_context = _ltm_svc.format_for_prompt(memories)
            except Exception as _ltm_exc:
                logger.debug("LTM recall skipped: %s", _ltm_exc)

        # RAG: retrieve relevant knowledge base context for this query
        rag_context = ""
        try:
            from app.services.rag_service import get_rag_service
            rag_context = get_rag_service().search_for_agent(db, agent_id, msg.text)
        except Exception as _rag_exc:
            logger.debug("RAG search skipped: %s", _rag_exc)

    # ── Outside DB session: web search + provider call (can be slow) ─────────

    loop = asyncio.get_running_loop()
    event_bus = get_event_bus()
    stream_id = str(uuid.uuid4())

    # Web search (before starting the stream so results go into system prompt)
    search_context = ""
    if agent_web_search:
        # Show typing while searching
        await context.bot.send_chat_action(chat_id=msg.chat.id, action="typing")
        results = await loop.run_in_executor(None, _search_svc.search, msg.text)
        search_context = _search_svc.format_for_context(results)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %d %B %Y, %H:%M UTC")
    system_parts = [f"Today's date and time: {date_str}"]
    if agent_system_prompt:
        system_parts.append(agent_system_prompt)
    # Add conversation summary if using summary mode
    if USE_SUMMARY_INSTEAD_OF_HISTORY and session_summary:
        system_parts.append(f"Previous conversation summary:\n{session_summary}")
    if ltm_context:
        system_parts.append(ltm_context)
    if rag_context:
        system_parts.append(rag_context)
    if search_context:
        system_parts.append(search_context)
    system = "\n\n".join(system_parts)

    optimization_plan = _token_optimizer.optimize_request(
        provider_type=provider_type,
        provider_name=provider_name,
        provider_config=provider_config,
        system=system,
        history=history,
        user_message=msg.text,
    )
    optimized_history = optimization_plan.history
    selected_model = optimization_plan.model
    selected_max_tokens = optimization_plan.max_output_tokens

    workspace_path = agent_workspace
    if agent_code_exec and not workspace_path:
        workspace_path = f"/app/workspaces/{agent_name}"
    use_streaming = not agent_code_exec  # tool-calling loop can't stream mid-turn

    # Set up stream buffer + event-bus relay
    stream_buf = _StreamBuffer(loop)
    stop_stream = asyncio.Event()

    def on_token(token: str) -> None:
        stream_buf.push(token)
        loop.call_soon_threadsafe(
            event_bus.publish_nowait,
            "stream.chunk",
            {"stream_id": stream_id, "channel": "telegram",
             "chat_id": msg.chat.id, "agent": agent_name, "token": token},
        )

    event_bus.publish_nowait(
        "stream.start",
        {"stream_id": stream_id, "channel": "telegram",
         "chat_id": msg.chat.id, "agent": agent_name},
    )

    # Start the streaming display task (for plain chat) or typing indicator (for tool-calls)
    if use_streaming:
        display_task = asyncio.create_task(
            _stream_to_telegram(context.bot, msg.chat.id, stream_buf, stop_stream)
        )
    else:
        display_task = asyncio.create_task(
            _typing_loop(context.bot, msg.chat.id, stop_stream)
        )

    reply_text = ""
    response_meta: dict = {
        "provider_name": provider_name,
        "provider_type": str(getattr(provider_type, "value", provider_type)),
        "optimizer": optimization_plan.as_meta(),
    }

    # Use async agent runner (non-blocking)
    _agent_runner_async = get_agent_runner_async()

    try:
        run_result = await _agent_runner_async.run_with_meta(
            msg.text,
            provider_type=provider_type,
            provider_name=provider_name,
            provider_config=provider_config,
            system=system,
            history=optimized_history,
            workspace_path=workspace_path if agent_code_exec else None,
            on_token=on_token if use_streaming else None,
            model=selected_model,
            max_tokens=selected_max_tokens,
        )
        reply_text = run_result.text
        
        # Логируем результат от провайдера
        logger.info(
            "Provider response agent=%s provider=%s model=%s text_length=%d",
            agent_name,
            provider_name,
            run_result.model or selected_model,
            len(reply_text) if reply_text else 0
        )

        if not reply_text:
            logger.warning(
                "Empty text from provider agent=%s provider=%s model=%s",
                agent_name,
                provider_name,
                run_result.model or selected_model
            )
        input_tokens = run_result.input_tokens or optimization_plan.estimated_input_tokens
        output_tokens = (
            run_result.output_tokens or _token_optimizer.estimate_text_tokens(reply_text)
        )
        estimated_cost = _token_optimizer.estimate_cost(
            provider_type=provider_type,
            provider_name=provider_name,
            provider_config=provider_config,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        response_meta["usage"] = {
            "model": run_result.model or selected_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(estimated_cost, 8),
            "estimated_tokens": bool(run_result.input_tokens <= 0 or run_result.output_tokens <= 0),
        }
        event_bus.publish_nowait(
            "stream.end",
            {"stream_id": stream_id, "channel": "telegram",
             "chat_id": msg.chat.id, "agent": agent_name, "chars": len(reply_text),
             "input_tokens": input_tokens, "output_tokens": output_tokens},
        )
    except Exception as exc:
        logger.error("Provider error for agent %s: %s", agent_name, exc, exc_info=True)
        # Fallback attempt only for retryable provider classes.
        fallback_result = None
        primary_exc = exc
        primary_provider_name = provider_name
        fallback_failures: list[tuple[str, Exception]] = []
        if _should_try_fallback(primary_exc):
            for candidate in provider_candidates:
                if candidate.name == provider_name:
                    continue
                try:
                    fallback_result = await _agent_runner_async.run_with_meta(
                        msg.text,
                        provider_type=candidate.type,
                        provider_name=candidate.name,
                        provider_config=dict(candidate.config),
                        system=system,
                        history=optimized_history,
                        workspace_path=workspace_path if agent_code_exec else None,
                        on_token=on_token if use_streaming else None,
                        model=None,
                        max_tokens=selected_max_tokens,
                    )
                    provider_name = candidate.name
                    provider_type = candidate.type
                    provider_config = dict(candidate.config)
                    response_meta["fallback"] = {
                        "from": primary_provider_name,
                        "to": candidate.name,
                    }
                    break
                except Exception as fallback_exc:
                    fallback_failures.append((candidate.name, fallback_exc))
                    logger.error("Fallback provider %s failed: %s", candidate.name, fallback_exc)

        if fallback_result is not None:
            run_result = fallback_result
            reply_text = run_result.text
            logger.info(
                "Fallback successful agent=%s from=%s to=%s text_length=%d",
                agent_name,
                primary_provider_name,
                provider_name,
                len(reply_text) if reply_text else 0
            )
            response_meta["provider_name"] = provider_name
            response_meta["provider_type"] = str(getattr(provider_type, "value", provider_type))
            input_tokens = run_result.input_tokens or optimization_plan.estimated_input_tokens
            output_tokens = (
                run_result.output_tokens or _token_optimizer.estimate_text_tokens(reply_text)
            )
            estimated_cost = _token_optimizer.estimate_cost(
                provider_type=provider_type,
                provider_name=provider_name,
                provider_config=provider_config,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            response_meta["usage"] = {
                "model": run_result.model or selected_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": round(estimated_cost, 8),
                "estimated_tokens": bool(run_result.input_tokens <= 0 or run_result.output_tokens <= 0),
            }
            event_bus.publish_nowait(
                "stream.end",
                {"stream_id": stream_id, "channel": "telegram",
                 "chat_id": msg.chat.id, "agent": agent_name, "chars": len(reply_text),
                 "input_tokens": input_tokens, "output_tokens": output_tokens},
            )
            event_bus.publish_nowait(
                "stream.fallback",
                {"stream_id": stream_id, "channel": "telegram",
                 "chat_id": msg.chat.id, "agent": agent_name,
                 "from": primary_provider_name, "to": provider_name},
            )
        else:
            error_id = uuid.uuid4().hex[:8]
            primary_info = _classify_provider_error(primary_exc)
            logger.error(
                "provider failure id=%s agent=%s provider=%s code=%s detail=%s",
                error_id,
                agent_name,
                primary_provider_name,
                primary_info.code,
                primary_info.detail,
                exc_info=primary_exc,
            )
            event_bus.publish_nowait(
                "stream.error",
                {"stream_id": stream_id, "channel": "telegram",
                 "chat_id": msg.chat.id, "agent": agent_name,
                 "error": str(primary_exc), "error_id": error_id},
            )
            response_meta["error"] = str(primary_exc)
            response_meta["error_id"] = error_id
            settings = get_settings()
            show_debug = settings.telegram_show_errors or settings.app_env != "prod"
            reply_text = _format_provider_error_message(
                provider_name=primary_provider_name,
                exc=primary_exc,
                debug=show_debug,
                error_id=error_id,
            )
            if fallback_failures:
                reply_text += "\n\nFallback провайдеры тоже не сработали:"
                for name, fexc in fallback_failures[:3]:
                    finfo = _classify_provider_error(fexc)
                    suffix = f" (HTTP {finfo.http_status})" if finfo.http_status else ""
                    line = f"\n- `{name}`: {finfo.code}{suffix}"
                    if show_debug:
                        line += f" | {finfo.detail}"
                    reply_text += line
                if len(fallback_failures) > 3:
                    reply_text += f"\n...и ещё {len(fallback_failures) - 3}"
            stop_stream.set()
            await display_task
            if not use_streaming or not stream_buf.get_text():
                logger.info("Sending error message to chat=%s error_id=%s", msg.chat.id, error_id)
                await msg.reply_text(reply_text)
            return
    finally:
        stop_stream.set()
        await display_task

    # For tool-calling mode the message wasn't sent yet; for streaming it was already edited
    if not use_streaming or not stream_buf.get_text():
        # Проверяем что ответ не пустой
        if not reply_text or not reply_text.strip():
            error_id = uuid.uuid4().hex[:8]
            logger.error(
                "Empty reply from provider agent=%s provider=%s error_id=%s",
                agent_name, provider_name, error_id
            )
            reply_text = (
                f"⚠️ Пустой ответ от провайдера `{provider_name}`.\n\n"
                f"Возможные причины:\n"
                f"• API ключ неверный или истёк\n"
                f"• Модель недоступна\n" 
                f"• Превышен лимит запросов\n\n"
                f"Проверьте настройки провайдера в админке.\n"
                f"Error ID: `{error_id}`"
            )
        logger.info("Sending reply to chat=%s length=%d", msg.chat.id, len(reply_text))
        await msg.reply_text(reply_text)
    else:
        logger.info("Streaming used, message already edited for chat=%s", msg.chat.id)

    # ── Save exchange to memory + cost tracking + LTM extraction ────────────
    if (
        agent_memory
        and session_id
        and not reply_text.startswith("Ошибка у провайдера `")
    ):
        with SessionLocal() as db:
            # Save full exchange if not using summary mode
            if not USE_SUMMARY_INSTEAD_OF_HISTORY:
                _memory_svc.save_exchange(
                    db,
                    session_id,
                    msg.text,
                    reply_text,
                    user_meta={"optimizer": optimization_plan.as_meta()},
                    assistant_meta=response_meta,
                    session_meta={
                        "last_token_usage": response_meta.get("usage", {}),
                        "last_optimizer": optimization_plan.as_meta(),
                    },
                )
            else:
                # Update lightweight summary instead of full history
                try:
                    _summary_svc(db).update_summary(session, msg.text, reply_text)
                except Exception as _sum_exc:
                    logger.debug("Summary update failed: %s", _sum_exc)
            # Cost tracking
            usage_data = response_meta.get("usage", {})
            if usage_data:
                try:
                    _cost_tracker.record(
                        db,
                        user_id=user.id if user else None,
                        agent_id=agent_id,
                        session_id=session_id,
                        model=usage_data.get("model", "unknown"),
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        cost_usd=usage_data.get("estimated_cost_usd", 0),
                        channel="telegram",
                    )
                except Exception as _cost_exc:
                    logger.debug("Cost tracking failed: %s", _cost_exc)
            # LTM extraction
            if user:
                try:
                    _ltm_svc.extract_and_store(
                        db, user.id, agent_id, msg.text, reply_text, session_id
                    )
                except Exception as _ltm_exc:
                    logger.debug("LTM extraction failed: %s", _ltm_exc)

    get_event_bus().publish_nowait(
        "task.telegram_message",
        {"bot": bot_username, "chat_id": msg.chat.id, "agent": agent_name},
    )


class TelegramGateway(GatewayAdapter):
    """Manages one Application per bot token."""

    def __init__(self, applications: list[Application]) -> None:
        self._apps = applications

    async def start(self) -> None:  # pragma: no cover
        for app in self._apps:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Started %d Telegram bot(s)", len(self._apps))

    async def stop(self) -> None:  # pragma: no cover
        for app in self._apps:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        logger.info("Telegram gateway stopped")


def build_telegram_gateway(tokens_csv: str) -> TelegramGateway:
    """Build one Application per comma-separated bot token."""
    applications: list[Application] = []
    for raw_token in tokens_csv.split(","):
        token = raw_token.strip()
        if not token:
            continue
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", _cmd_start))
        app.add_handler(CommandHandler("help", _cmd_help))
        app.add_handler(CommandHandler("new", _cmd_new))
        app.add_handler(CommandHandler("settings", _cmd_settings))
        app.add_handler(CommandHandler("status", _cmd_status))
        app.add_handler(CommandHandler("whoami", _cmd_whoami))
        app.add_handler(CommandHandler("pair", _cmd_pair))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
        app.add_error_handler(_error_handler)
        applications.append(app)

    if not applications:
        raise ValueError("No valid Telegram bot tokens provided")

    return TelegramGateway(applications)
