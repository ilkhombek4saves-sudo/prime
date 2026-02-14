"""
Telegram Bot Integration — Full bidirectional bot with long-polling and webhook support.
Bot: @gpuvpsopenclawbot
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from prime.config.settings import settings
from prime.core.agent import Agent

TOKEN = settings.TELEGRAM_TOKEN
API = f"https://api.telegram.org/bot{TOKEN}"


# ─── Telegram API Helpers ─────────────────────────────────────────────────────
def _post(method: str, data: dict = None) -> dict:
    url = f"{API}/{method}"
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get(method: str, params: dict = None) -> dict:
    url = f"{API}/{method}"
    if params:
        import urllib.parse
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(chat_id: str | int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send message, splitting if > 4096 chars."""
    MAX = 4000
    if len(text) <= MAX:
        return _post("sendMessage", {
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
        })
    # Split into chunks
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    result = {}
    for chunk in chunks:
        result = _post("sendMessage", {
            "chat_id": chat_id, "text": chunk, "parse_mode": parse_mode,
        })
        time.sleep(0.3)
    return result


def send_typing(chat_id: str | int) -> None:
    _post("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def set_webhook(url: str) -> dict:
    return _post("setWebhook", {"url": url})


def delete_webhook() -> dict:
    return _post("deleteWebhook", {})


def get_updates(offset: int = 0, timeout: int = 30) -> list[dict]:
    data = _get("getUpdates", {"offset": offset, "timeout": timeout, "limit": 100})
    if data.get("ok"):
        return data.get("result", [])
    return []


# ─── DM Policy ────────────────────────────────────────────────────────────────
# Control who can interact with the bot.
#
# Modes (set DM_POLICY env var):
#   open      — anyone can use the bot (default for dev)
#   allowlist — only TELEGRAM_ALLOWED_IDS users
#   pairing   — unknown users get a pairing request; admin approves via /approve
#
# TELEGRAM_ALLOWED_IDS — comma-separated Telegram user IDs (e.g. "123456,789012")
# TELEGRAM_ADMIN_CHAT_ID — where pairing requests are sent (defaults to TELEGRAM_CHAT_ID)

import os as _os

_DM_POLICY = _os.getenv("DM_POLICY", "allowlist").lower()  # open | allowlist | pairing
_ALLOWED_IDS: set[int] = {
    int(x.strip())
    for x in _os.getenv("TELEGRAM_ALLOWED_IDS", settings.TELEGRAM_CHAT_ID).split(",")
    if x.strip().lstrip("-").isdigit()
}
_ADMIN_CHAT_ID: int | None = int(settings.TELEGRAM_CHAT_ID) if settings.TELEGRAM_CHAT_ID else None

# Pending pairing requests: user_id → {name, chat_id, ts}
_pairing_pending: dict[int, dict] = {}


def _dm_decision(user_id: int, chat_id: int, user: dict) -> tuple[bool, str]:
    """Return (allowed, reason). Handles all three DM policy modes."""
    if _DM_POLICY == "open":
        return True, "open"

    if _DM_POLICY == "allowlist":
        if user_id in _ALLOWED_IDS or chat_id in _ALLOWED_IDS:
            return True, "allowlist"
        return False, "not_in_allowlist"

    # pairing mode
    if user_id in _ALLOWED_IDS or chat_id in _ALLOWED_IDS:
        return True, "allowlisted"
    if user_id in _pairing_pending:
        return False, "pairing_pending"
    # First time — send pairing request to admin
    name = user.get("first_name", "") + " " + user.get("last_name", "")
    username = user.get("username", "")
    _pairing_pending[user_id] = {"name": name.strip(), "chat_id": chat_id, "username": username}
    if _ADMIN_CHAT_ID and _ADMIN_CHAT_ID != chat_id:
        send_message(
            _ADMIN_CHAT_ID,
            f"🔔 *Запрос на доступ*\n\n"
            f"• Имя: {name.strip() or '?'}\n"
            f"• Username: @{username or '?'}\n"
            f"• user\\_id: `{user_id}`\n"
            f"• chat\\_id: `{chat_id}`\n\n"
            f"Одобрить: `/approve {user_id}`\n"
            f"Отклонить: `/deny {user_id}`",
        )
    return False, "pairing_requested"


def _denied_message(reason: str, user: dict) -> str:
    name = user.get("first_name", "пользователь")
    if reason == "pairing_requested":
        return (
            f"👋 Привет, {name}!\n\n"
            "🔒 Этот бот приватный. Запрос на доступ отправлен администратору.\n"
            "Ожидайте одобрения — вас уведомят."
        )
    if reason == "pairing_pending":
        return "⏳ Ваш запрос на рассмотрении у администратора. Ожидайте."
    if reason == "not_in_allowlist":
        return (
            f"🚫 Привет, {name}!\n\n"
            "У вас нет доступа к этому боту.\n"
            f"Ваш Telegram ID: `{user.get('id', '?')}`\n"
            "Обратитесь к администратору."
        )
    return "🚫 Доступ запрещён."


# ─── Agent Sessions per chat ──────────────────────────────────────────────────
_sessions: dict[int, Agent] = {}


def _get_agent(chat_id: int, user_id: int = None) -> Agent:
    if chat_id not in _sessions:
        _sessions[chat_id] = Agent(
            session_id=f"tg-{chat_id}",
            channel="telegram",
            user_id=str(user_id or chat_id),
        )
    return _sessions[chat_id]


# ─── Command Handlers ─────────────────────────────────────────────────────────
def handle_command(cmd: str, chat_id: int, user: dict, args: str = "") -> str:
    # Admin-only: /approve and /deny (only from admin chat)
    if cmd in ("/approve", "/deny") and chat_id == _ADMIN_CHAT_ID:
        try:
            target_id = int(args.strip())
        except (ValueError, TypeError):
            return "Usage: /approve <user_id>  or  /deny <user_id>"

        if cmd == "/approve":
            pending = _pairing_pending.pop(target_id, None)
            _ALLOWED_IDS.add(target_id)
            if pending:
                send_message(
                    pending["chat_id"],
                    "✅ Доступ одобрен! Теперь вы можете использовать бота.\nНапишите /start",
                )
            return f"✅ Пользователь `{target_id}` одобрен и добавлен в allowlist."
        else:  # /deny
            pending = _pairing_pending.pop(target_id, None)
            if pending:
                send_message(pending["chat_id"], "🚫 В доступе отказано.")
            return f"❌ Пользователю `{target_id}` отказано."

    if cmd == "/start":
        name = user.get("first_name", "друг")
        return (
            f"👋 Привет, {name}!\n\n"
            f"Я **Prime** — ваш AI-агент с полным доступом к серверу.\n\n"
            f"Я могу:\n"
            f"• 📁 Читать и редактировать файлы\n"
            f"• 💻 Выполнять shell команды\n"
            f"• 🔍 Искать в интернете\n"
            f"• 🧠 Запоминать информацию\n"
            f"• ✍️ Писать и запускать код\n\n"
            f"Просто напишите мне что нужно сделать!"
        )
    elif cmd == "/status":
        from prime.core.agent import get_system_info
        info = get_system_info()
        provider = settings.best_provider() or "none"
        return (
            f"🖥 *Prime Status*\n\n"
            f"• Host: `{info['hostname']}`\n"
            f"• OS: `{info['os']}`\n"
            f"• Env: `{info['environment']}`\n"
            f"• Provider: `{provider}`\n"
            f"• APIs: `{', '.join(settings.available_providers()) or 'none'}`\n"
        )
    elif cmd == "/help":
        return (
            "🤖 *Prime Commands*\n\n"
            "/start — Приветствие\n"
            "/status — Статус системы\n"
            "/memory — Ваши заметки\n"
            "/reset — Сбросить разговор\n"
            "/help — Помощь\n\n"
            "Или просто напишите любой вопрос!"
        )
    elif cmd == "/memory":
        try:
            from prime.core.memory import get_db
            mems = get_db().list_memories(str(chat_id))
            if not mems:
                return "🧠 Память пуста. Скажите мне что-нибудь запомнить!"
            lines = ["🧠 *Ваши заметки:*\n"]
            for m in mems[:10]:
                lines.append(f"• *{m['key']}*: {m['content'][:100]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"
    elif cmd == "/reset":
        if chat_id in _sessions:
            del _sessions[chat_id]
        return "✅ Разговор сброшен. Начнём заново!"
    return f"Неизвестная команда: {cmd}"


# ─── Update Handler ───────────────────────────────────────────────────────────
async def handle_update(update: dict) -> None:
    """Process a single Telegram update."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    user_id = user.get("id", chat_id)
    text = message.get("text", "").strip()

    if not text:
        return

    if text.startswith("/"):
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/approve", "/deny"):
            response = handle_command(cmd, chat_id, user, args)
            send_message(chat_id, response)
            return

        allowed, reason = _dm_decision(user_id, chat_id, user)
        if not allowed:
            send_message(chat_id, _denied_message(reason, user))
            return
        response = handle_command(cmd, chat_id, user, args)
        send_message(chat_id, response)
        return

    # Regular message — enforce DM policy
    allowed, reason = _dm_decision(user_id, chat_id, user)
    if not allowed:
        send_message(chat_id, _denied_message(reason, user))
        return

    send_typing(chat_id)
    agent = _get_agent(chat_id, user_id)
    response = await asyncio.to_thread(agent.chat, text)
    send_message(chat_id, response)


def process_update_sync(update: dict) -> None:
    """Synchronous version for the polling loop."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    user_id = user.get("id", chat_id)
    text = message.get("text", "").strip()

    if not text:
        return

    # /start and admin /approve /deny bypass DM policy check
    if text.startswith("/"):
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Admin commands never blocked
        if cmd in ("/approve", "/deny"):
            response = handle_command(cmd, chat_id, user, args)
            send_message(chat_id, response)
            return

        # /start always gets a response (policy check inside)
        if cmd == "/start":
            allowed, reason = _dm_decision(user_id, chat_id, user)
            if not allowed:
                send_message(chat_id, _denied_message(reason, user))
                return
            response = handle_command(cmd, chat_id, user, args)
            send_message(chat_id, response)
            return

        # All other commands — enforce policy
        allowed, reason = _dm_decision(user_id, chat_id, user)
        if not allowed:
            send_message(chat_id, _denied_message(reason, user))
            return
        response = handle_command(cmd, chat_id, user, args)
        send_message(chat_id, response)
        return

    # Regular message — enforce DM policy
    allowed, reason = _dm_decision(user_id, chat_id, user)
    if not allowed:
        send_message(chat_id, _denied_message(reason, user))
        return

    send_typing(chat_id)
    agent = _get_agent(chat_id, user_id)
    response = agent.chat(text)
    send_message(chat_id, response)


# ─── Long Polling Loop ────────────────────────────────────────────────────────
def run_polling():
    """Start Telegram long-polling loop. Blocking."""
    print(f"  → Telegram bot starting (long-polling)...")
    print(f"  → Bot token: {TOKEN[:20]}...")

    # Verify token
    me = _get("getMe")
    if me.get("ok"):
        bot = me["result"]
        print(f"  ✓ Bot: @{bot.get('username')} ({bot.get('first_name')})")
    else:
        print(f"  ✗ Invalid token: {me}")
        return

    offset = 0
    while True:
        try:
            updates = get_updates(offset=offset, timeout=30)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = max(offset, update_id + 1)
                try:
                    process_update_sync(update)
                except Exception as e:
                    print(f"  ✗ Update error: {e}")
        except KeyboardInterrupt:
            print("\n  → Telegram bot stopped.")
            break
        except Exception as e:
            print(f"  ✗ Polling error: {e}")
            time.sleep(5)


# ─── Notification (outbound) ──────────────────────────────────────────────────
def notify(message: str, chat_id: str = None) -> bool:
    """Send a notification to the configured chat."""
    cid = chat_id or settings.TELEGRAM_CHAT_ID
    if not cid:
        # Try loading from config
        cfg_file = Path.home() / ".config" / "prime" / "telegram_chat.json"
        if cfg_file.exists():
            try:
                cid = json.loads(cfg_file.read_text()).get("chat_id", "")
            except Exception:
                pass
    if not cid:
        print("  ✗ No Telegram chat_id configured")
        return False
    result = send_message(cid, message)
    return result.get("ok", False)


if __name__ == "__main__":
    run_polling()
