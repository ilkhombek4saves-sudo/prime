#!/usr/bin/env python3
"""
Prime Telegram Bot - Minimal Version
"""
import os
import sys
import json
import urllib.request
import subprocess
import time

os.environ['DEEPSEEK_API_KEY'] = 'sk-85f89945161646beb062d578f1974581'

TOKEN = "8594140376:AAE_7TOl9N2GyATz4U8zbe5C-OgvT9DD8ho"
CHAT_ID = "1267937858"

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"Send error: {e}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GetUpdates error: {e}")
        return {"ok": False}

def call_prime(query):
    try:
        result = subprocess.run(
            ['./prime', '--provider', 'deepseek', query],
            capture_output=True, text=True, timeout=120,
            cwd='/home/ilkhombek4saves/prime'
        )
        return result.stdout.strip() or result.stderr.strip() or "(no output)"
    except Exception as e:
        return f"Error: {e}"

print("🚀 Prime Bot started")
send("🤖 Prime Bot запущен!\n\nОтправьте сообщение для тестирования.")

offset = None
while True:
    try:
        data = get_updates(offset)
        if not data.get('ok'):
            time.sleep(5)
            continue
        
        for update in data.get('result', []):
            offset = update['update_id'] + 1
            msg = update.get('message', {})
            text = msg.get('text', '')
            chat = msg.get('chat', {}).get('id')
            
            if text and chat:
                print(f"Got: {text[:50]}")
                
                if text == '/start':
                    send("🤖 Prime Bot\n\nЯ готов к работе!")
                elif text == '/status':
                    send("✅ Prime Bot работает\nПровайдер: DeepSeek")
                else:
                    send("⏳ Обработка...")
                    response = call_prime(text)
                    send(response[:4000])
        
        time.sleep(2)
    except KeyboardInterrupt:
        send("🛑 Bot stopped")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
