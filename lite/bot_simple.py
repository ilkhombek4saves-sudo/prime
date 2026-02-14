#!/usr/bin/env python3
"""
Prime Telegram Bot - Simple Subprocess Version
"""
import json
import urllib.request
import subprocess
import time
import os

TOKEN = "8594140376:AAE_7TOl9N2GyATz4U8zbe5C-OgvT9DD8ho"

def send(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"Send error: {e}")

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?limit=10"
        if offset:
            url += f"&offset={offset}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GetUpdates error: {e}")
        return {"ok": False}

def call_prime(query):
    # Clean ANSI escape sequences from query if present
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_query = ansi_escape.sub('', query)
    
    env = os.environ.copy()
    env['DEEPSEEK_API_KEY'] = 'sk-85f89945161646beb062d578f1974581'
    try:
        result = subprocess.run(
            ['python3', 'lite/prime-lite.py', '--provider', 'deepseek', clean_query],
            capture_output=True, text=True, timeout=6000,
            cwd='/home/ilkhombek4saves/prime',
            env=env
        )
        return result.stdout.strip()[:4000] or "(empty)"
    except Exception as e:
        return f"Error: {e}"

print("Prime Bot started")
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
            chat_id = msg.get('chat', {}).get('id')
            
            if not text or not chat_id:
                continue
            
            print(f"Got from {chat_id}: {text[:50]}")
            
            if text == '/start':
                send(chat_id, "🤖 Prime Bot ready!")
            elif text == '/status':
                send(chat_id, "✅ Bot is running")
            else:
                response = call_prime(text)
                send(chat_id, response)
        
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
