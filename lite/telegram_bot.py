#!/usr/bin/env python3
"""
Prime Telegram Bot
Отправляет ответы в Telegram вместо stdout
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

# Telegram token из .env
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "8594140376:AAETXfUNUCPKOMvO1TVYm_cKbbTgTBap9FQ"


def send_telegram_message(chat_id: str, text: str, parse_mode="Markdown"):
    """Send message to Telegram chat"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text[:4000],  # Telegram limit
            "parse_mode": parse_mode
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
            return resp.get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


def get_updates(offset=None):
    """Get updates from Telegram (for webhook mode)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        if offset:
            url += f"?offset={offset}"
        
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Error getting updates: {e}", file=sys.stderr)
        return {"ok": False}


def format_response(text: str) -> str:
    """Format response for Telegram"""
    # Escape markdown special chars
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text


def notify_user(message: str, chat_id: str = None):
    """Send notification to user via Telegram"""
    # Default chat ID - можно получить из конфига или передать явно
    if not chat_id:
        # Пытаемся получить из файла конфига
        config_file = Path.home() / ".config" / "prime" / "telegram_chat.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                chat_id = data.get("chat_id")
            except:
                pass
    
    if not chat_id:
        print("Telegram chat_id not configured. Run setup first.")
        return False
    
    return send_telegram_message(chat_id, message)


def setup_chat_id():
    """Setup Telegram chat ID by polling for messages"""
    print("Starting Telegram setup...")
    print("1. Send any message to your bot in Telegram")
    print("2. Waiting for message...")
    
    import time
    offset = None
    
    for attempt in range(30):  # Wait up to 60 seconds
        updates = get_updates(offset)
        
        if updates.get("ok") and updates.get("result"):
            for update in updates["result"]:
                offset = update["update_id"] + 1
                
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    username = msg["chat"].get("username", "unknown")
                    
                    print(f"\n✓ Got message from @{username}")
                    print(f"✓ Chat ID: {chat_id}")
                    
                    # Save config
                    config_file = Path.home() / ".config" / "prime" / "telegram_chat.json"
                    config_file.parent.mkdir(parents=True, exist_ok=True)
                    config_file.write_text(json.dumps({"chat_id": chat_id, "username": username}))
                    
                    # Send test message
                    send_telegram_message(
                        chat_id, 
                        "✅ *Prime Bot Connected!*\n\nI can now send you responses here.",
                        parse_mode="Markdown"
                    )
                    
                    print("✓ Configuration saved!")
                    print(f"✓ Test message sent to Telegram")
                    return True
        
        time.sleep(2)
        print(f"... waiting ({attempt + 1}/30)")
    
    print("\n✗ Timeout: No message received")
    print("Make sure you:")
    print("1. Started the bot by sending /start in Telegram")
    print("2. Sent any message to the bot")
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 telegram_bot.py setup          # Setup Telegram chat")
        print("  python3 telegram_bot.py send 'Hello'   # Send test message")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "setup":
        setup_chat_id()
    elif cmd == "send":
        message = " ".join(sys.argv[2:])
        if notify_user(message):
            print("Message sent!")
        else:
            print("Failed to send message")
    else:
        print(f"Unknown command: {cmd}")
