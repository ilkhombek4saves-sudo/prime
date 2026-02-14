#!/usr/bin/env python3
"""
Prime Telegram Bot (Simple Polling)
Вызывает ./prime напрямую через subprocess
"""
import os
import sys
import json
import urllib.request
import subprocess
import time

TELEGRAM_TOKEN = "8594140376:AAE_7TOl9N2GyATz4U8zbe5C-OgvT9DD8ho"
PRIME_DIR = "/home/ilkhombek4saves/prime"
DEFAULT_PROVIDER = "deepseek"

os.environ['DEEPSEEK_API_KEY'] = 'sk-85f89945161646beb062d578f1974581'
os.environ['KIMI_API_KEY'] = 'sk-oOP4eUYONqLJ2Y0AXXbN1Sj85MS2kdBHz7RmEO3L56kzSEHY'
os.environ['GEMINI_API_KEY'] = 'AQ.Ab8RN6Klpl5ntemc5gofexDUXUyHxS7EeETOgz7KWEOyiF82QA'


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
        return {"ok": False}


def send_message(chat_id, text):
    """Отправка сообщения"""
    # Экранируем спецсимволы для Markdown
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return api_request("sendMessage", {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": "MarkdownV2"
    })


def send_plain_message(chat_id, text):
    """Отправка без форматирования"""
    return api_request("sendMessage", {
        "chat_id": chat_id,
        "text": text[:4000]
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


def call_prime(query):
    """Вызов Prime CLI"""
    try:
        result = subprocess.run(
            ['./prime', '--provider', DEFAULT_PROVIDER, query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PRIME_DIR
        )
        
        output = result.stdout.strip()
        if result.stderr:
            output += "\n\n[stderr]: " + result.stderr.strip()
        
        return output if output else "(пустой ответ)"
    except subprocess.TimeoutExpired:
        return "⏱️ Таймаут: запрос занял слишком много времени"
    except Exception as e:
        return f"❌ Ошибка: {e}"


def handle_command(chat_id, text):
    """Обработка команд"""
    if text == '/start':
        return (
            "🤖 *Prime Bot*\\n\\n"
            "Я AI\\-ассистент с полным доступом к системе\\.\\n\\n"
            "*Команды:*\\n"
            "`/status` \\u2013 статус системы\\n"
            "`/help` \\u2013 помощь\\n"
            "`/provider` \\u2013 сменить провайдера\\n\\n"
            "Просто напиши мне что угодно\\!"
        ), True
    
    if text == '/help':
        return (
            "*Prime Help*\\n\\n"
            "*Могу делать:*\\n"
            "• 📁 Читать файлы\\n"
            "• ⚡ Выполнять команды\\n"
            "• 🌐 Искать в интернете\\n"
            "• 🛠️ Помогать с кодом\\n\\n"
            "*Примеры:*\\n"
            "`Покажи файлы`\\n"
            "`Прочитай README\\.md`\\n"
            "`Запусти ls \\u2011la`"
        ), True
    
    if text == '/status':
        import subprocess
        hostname = subprocess.getoutput('hostname')
        uptime = subprocess.getoutput('uptime -p')
        
        return (
            f"🖥️ *Prime Status*\\n\\n"
            f"*Сервер:* `{hostname}`\\n"
            f"*Uptime:* {uptime}\\n"
            f"*Провайдер:* `{DEFAULT_PROVIDER}`"
        ), True
    
    return None, False


def main():
    print("🚀 Prime Telegram Bot")
    print(f"🤖 Бот: @gpuvpsopenclawbot")
    print(f"🔧 Провайдер: {DEFAULT_PROVIDER}")
    print(f"📁 Prime dir: {PRIME_DIR}")
    print("\n⏳ Ожидание сообщений...")
    print("Нажмите Ctrl+C для остановки\n")
    
    offset = None
    
    while True:
        try:
            result = get_updates(offset)
            
            if not result.get('ok'):
                print(f"[Error] getUpdates failed")
                time.sleep(5)
                continue
            
            updates = result.get('result', [])
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' not in update:
                    continue
                
                message = update['message']
                chat_id = message.get('chat', {}).get('id')
                text = message.get('text', '')
                
                if not text or not chat_id:
                    continue
                
                print(f"[Message] {chat_id}: {text[:50]}")
                
                # Проверяем команды
                response, is_command = handle_command(chat_id, text)
                
                if not response:
                    # Показываем typing
                    send_chat_action(chat_id)
                    # Вызываем Prime
                    response = call_prime(text)
                
                # Отправляем ответ
                if response:
                    if is_command:
                        send_message(chat_id, response)
                    else:
                        send_plain_message(chat_id, response)
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Бот остановлен")
            break
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
