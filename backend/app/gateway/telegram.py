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
import traceback
import uuid

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.gateway.base import GatewayAdapter
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Bot, Provider, Session, SessionStatus, User, UserRole
from app.services.agent_runner import AgentRunner
from app.services.binding_resolver import BindingResolver
from app.services.dm_policy import DMPolicyService
from app.services.event_bus import get_event_bus
from app.services.memory_service import MemoryService
from app.services.token_optimizer import TokenOptimizationService
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

_memory_svc = MemoryService()
_search_svc = WebSearchService()
_agent_runner = AgentRunner()
_token_optimizer = TokenOptimizationService()


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
        logger.error("handle_message error: %s\n%s", exc, traceback.format_exc())
        if update.message:
            await update.message.reply_text("Ошибка обработки сообщения.")


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
            await msg.reply_text("No provider configured for this agent.")
            return

        provider_record: Provider | None = db.get(Provider, provider_id)
        if not provider_record or not provider_record.active:
            await msg.reply_text("Provider not available.")
            return

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

        # Load conversation history while DB is still open
        history: list[dict] = []
        if agent_memory and session_id:
            history = _memory_svc.get_history(db, session_id, agent_max_history)

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

    system_parts = []
    if agent_system_prompt:
        system_parts.append(agent_system_prompt)
    if rag_context:
        system_parts.append(rag_context)
    if search_context:
        system_parts.append(search_context)
    system = "\n\n".join(system_parts) if system_parts else None

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
    try:
        run_result = await loop.run_in_executor(
            None,
            lambda: _agent_runner.run_with_meta(
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
            ),
        )
        reply_text = run_result.text
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
        event_bus.publish_nowait(
            "stream.error",
            {"stream_id": stream_id, "channel": "telegram",
             "chat_id": msg.chat.id, "agent": agent_name, "error": str(exc)},
        )
        response_meta["error"] = str(exc)
        reply_text = "Sorry, something went wrong. Please try again."
    finally:
        stop_stream.set()
        await display_task

    # For tool-calling mode the message wasn't sent yet; for streaming it was already edited
    if not use_streaming or not stream_buf.get_text():
        await msg.reply_text(reply_text)

    # ── Save exchange to memory ───────────────────────────────────────────────
    if (
        agent_memory
        and session_id
        and reply_text != "Sorry, something went wrong. Please try again."
    ):
        with SessionLocal() as db:
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
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
        app.add_error_handler(_error_handler)
        applications.append(app)

    if not applications:
        raise ValueError("No valid Telegram bot tokens provided")

    return TelegramGateway(applications)
