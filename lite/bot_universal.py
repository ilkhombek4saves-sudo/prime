#!/usr/bin/env python3
"""
Prime Telegram Bot - Universal (отвечает в любой чат)
"""
import os
import sys
import json
import urllib.request
import subprocess
import time

os.environ['DEEPSEEK_API_KEY'] = 'sk-85f89945161646beb062d578f1974581'
os.environ['KIMI_API_KEY'] = 'sk-oOP4eUYONqLJ2Y0AXXbN1Sj85MS2kdBHz7RmEO3L56kzSEHY'

TOKEN = "8594140376:AAE_7TOl9N2GyATz4U8zbe5C-OgvT9DD8ho"
PROVIDER = "deepseek"

def send(chat_id, msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": msg[:4000]}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30)
        print(f"[Sent to {chat_id}]: {msg[:50]}...")
    except Exception as e:
        print(f"[Send error]: {e}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?limit=10"
    if offset:
        url += f"&offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[GetUpdates error]: {e}")
        return {"ok": False}

def call_prime(query):
    try:
        result = subprocess.run(
            ['./prime', '--provider', PROVIDER, query],
            capture_output=True, text=True, timeout=120,
            cwd='/home/ilkhombek4saves/prime'
        )
        out = result.stdout.strip()
        if not out and result.stderr:
            out = result.stderr.strip()
        return out or "(пустой ответ)"
    except subprocess.TimeoutExpired:
        return "⏱️ Таймаут"
    except Exception as e:
        return f"❌ Ошибка: {e}"

print("="*50)
print("🚀 Prime Telegram Bot")
print(f"🤖 Token: {TOKEN[:20]}...")
print(f"🔧 Provider: {PROVIDER}")
print("="*50)
print("⏳ Ожидание сообщений...")
print("Нажмите Ctrl+C для остановки")
print("="*50)

offset = None
message_count = 0

while True:
    try:
        data = get_updates(offset)
        
        if not data.get('ok'):
            print(f"[!] getUpdates failed: {data}")
            time.sleep(5)
            continue
        
        updates = data.get('result', [])
        
        if updates:
            print(f"[✓] Получено {len(updates)} сообщений")
        
        for update in updates:
            offset = update['update_id'] + 1
            message_count += 1
            
            msg = update.get('message', {})
            text = msg.get('text', '')
            chat = msg.get('chat', {})
            chat_id = chat.get('id')
            username = chat.get('username', 'unknown')
            
            if not text or not chat_id:
                continue
            
            print(f"\n[{message_count}] @{username} ({chat_id}): {text[:60]}")
            
            # Команды
            if text == '/start':
                send(chat_id, 
                    "🤖 *Prime Bot*\n\n"
                    "Я AI-ассистент с доступом к системе.\n\n"
                    "Команды:\n"
                    "/status — статус\n"
                    "/help — помощь\n\n"
                    "Просто напиши мне что-нибудь!"
                )
            
            elif text == '/status':
                import socket
                hostname = socket.gethostname()
                send(chat_id, 
                    f"🖥️ *Prime Status*\n\n"
                    f"Сервер: `{hostname}`\n"
                    f"Провайдер: `{PROVIDER}`\n"
                    f"Сообщений: {message_count}"
                )
            
            elif text == '/help':
                send(chat_id,
                    "*Что я умею:*\n\n"
                    "• Читать файлы\n"
                    "• Выполнять команды\n" 
                    "• Искать в интернете\n"
                    "• Помогать с кодом\n\n"
                    "Просто напиши запрос!"
                )
            
            else:
                # Отправляем "печатает"
                try:
                    url = f"https://api.telegram.org/bot{TOKEN}/sendChatAction"
                    data = json.dumps({"chat_id": chat_id, "action": "typing"}).encode()
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                except:
                    pass
                
                # Обрабатываем через Prime
                print(f"[→] Обработка через Prime...")
                response = call_prime(text)
                print(f"[←] Ответ: {response[:100]}...")
                send(chat_id, response)
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен")
        break
    except Exception as e:
        print(f"\n[!] Ошибка: {e}")
        time.sleep(5)
