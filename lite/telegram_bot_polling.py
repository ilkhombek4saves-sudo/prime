#!/usr/bin/env python3
"""
Prime Telegram Bot (Long Polling)
Работает без webhook, получает сообщения через getUpdates
"""
import os
import sys
import json
import urllib.request
import time
from pathlib import Path

# Добавляем путь к Prime
PRIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PRIME_DIR))
sys.path.insert(0, str(PRIME_DIR / "lite"))

# Импортируем напрямую
exec(open(PRIME_DIR / "lite" / "prime-lite.py").read().split('if __name__ == "__main__":')[0])

# Теперь классы доступны
AgentLoop = globals()['AgentLoop']

TELEGRAM_TOKEN = "8594140376:AAETXfUNUCPKOMvO1TVYm_cKbbTgTBap9FQ"
DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-chat"


def api_request(method, data=None):
    """Вызов метода Telegram API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    
    if data:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
    else:
        req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[API Error] {method}: {e}")
        return {"ok": False, "error": str(e)}


def send_message(chat_id, text):
    """Отправка сообщения"""
    return api_request("sendMessage", {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": "Markdown"
    })


def send_chat_action(chat_id, action='typing'):
    """Отправка статуса"""
    return api_request("sendChatAction", {
        "chat_id": chat_id,
        "action": action
    })


def get_updates(offset=None):
    """Получение новых сообщений"""
    params = {"limit": 100, "timeout": 30}
    if offset:
        params["offset"] = offset
    
    return api_request("getUpdates", params)


def handle_command(chat_id, text):
    """Обработка команд"""
    if text == '/start':
        return (
            "🤖 *Prime Bot*\n\n"
            "Я AI-ассистент с полным доступом к системе.\n\n"
            "*Команды:*\n"
            "`/status` - статус системы\n"
            "`/help` - помощь\n\n"
            "Просто напиши мне что угодно!"
        )
    
    if text == '/help':
        return (
            "*Prime Help*\n\n"
            "*Могу делать:*\n"
            "• 📁 Читать файлы\n"
            "• ⚡ Выполнять команды\n"
            "• 🌐 Искать в интернете\n"
            "• 🛠️ Помогать с кодом\n\n"
            "*Примеры:*\n"
            "`Покажи файлы в папке`\n"
            "`Прочитай README.md`\n"
            "`Запусти ls -la`\n"
            "`Найди информацию о Python`"
        )
    
    if text == '/status':
        import subprocess
        hostname = subprocess.getoutput('hostname')
        uptime = subprocess.getoutput('uptime -p')
        
        return (
            f"🖥️ *Prime Status*\n\n"
            f"*Сервер:* `{hostname}`\n"
            f"*Uptime:* {uptime}\n"
            f"*Провайдер:* `{DEFAULT_PROVIDER}`\n"
            f"*Модель:* `{DEFAULT_MODEL}`"
        )
    
    return None


def process_message(chat_id, text):
    """Обработка сообщения через Prime"""
    # Проверяем команды
    response = handle_command(chat_id, text)
    if response:
        return response
    
    # Обрабатываем через Prime Agent
    try:
        agent = AgentLoop(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL)
        response = agent.chat(text)
        return response
    except Exception as e:
        print(f"[Error] Prime: {e}")
        return f"❌ Ошибка: {e}"


def main():
    print("🚀 Prime Telegram Bot (Long Polling)")
    print(f"🤖 Бот: @gpuvpsopenclawbot")
    print(f"🔧 Провайдер: {DEFAULT_PROVIDER}")
    print("\n⏳ Ожидание сообщений...")
    print("Нажмите Ctrl+C для остановки\n")
    
    offset = None
    
    while True:
        try:
            result = get_updates(offset)
            
            if not result.get('ok'):
                print(f"[Error] getUpdates: {result}")
                time.sleep(5)
                continue
            
            updates = result.get('result', [])
            
            for update in updates:
                # Обновляем offset
                offset = update['update_id'] + 1
                
                # Пропускаем не-сообщения
                if 'message' not in update:
                    continue
                
                message = update['message']
                chat_id = message.get('chat', {}).get('id')
                text = message.get('text', '')
                
                if not text or not chat_id:
                    continue
                
                print(f"[Message] {chat_id}: {text[:50]}")
                
                # Показываем typing
                send_chat_action(chat_id)
                
                # Обрабатываем
                response = process_message(chat_id, text)
                
                # Отправляем ответ
                if response:
                    send_message(chat_id, response)
            
            # Небольшая пауза
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Бот остановлен")
            break
        except Exception as e:
            print(f"[Error] Main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
