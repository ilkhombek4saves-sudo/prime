#!/usr/bin/env python3
"""
Prime Telegram Bot Server
Принимает webhook от Telegram и обрабатывает через Prime
"""
import os
import sys
import json
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Добавляем путь к Prime
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "lite"))

from prime_lite import AgentLoop, build_system_prompt, TOOLS

TELEGRAM_TOKEN = "8594140376:AAETXfUNUCPKOMvO1TVYm_cKbbTgTBap9FQ"
DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-chat"

class TelegramHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Обрабатываем сообщение
            self.handle_update(data)
            
            # Отвечаем Telegram OK
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Prime Telegram Bot Server is running")
    
    def handle_update(self, data):
        """Обработка входящего сообщения"""
        message = data.get('message', {})
        if not message:
            return
        
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if not text or not chat_id:
            return
        
        print(f"[Telegram] Message from {chat_id}: {text[:50]}")
        
        # Специальные команды
        if text == '/start':
            self.send_message(chat_id, 
                "🤖 *Prime Bot*\n\n"
                "Я AI-ассистент с доступом к системе.\n\n"
                "*Доступные команды:*\n"
                "`/status` - статус системы\n"
                "`/help` - помощь\n\n"
                "Просто напиши мне что угодно!"
            )
            return
        
        if text == '/status':
            self.send_status(chat_id)
            return
        
        if text == '/help':
            self.send_message(chat_id,
                "*Prime Help*\n\n"
                "Я могу:\n"
                "• Читать файлы\n"
                "• Выполнять команды\n"
                "• Искать в интернете\n"
                "• Работать с кодом\n\n"
                "Примеры:\n"
                "`Покажи файлы`\n"
                "`Прочитай README.md`\n"
                "`Запусти ls -la`"
            )
            return
        
        # Отправляем "typing"
        self.send_chat_action(chat_id, 'typing')
        
        # Обрабатываем через Prime
        try:
            agent = AgentLoop(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL)
            response = agent.chat(text)
            
            # Отправляем ответ
            self.send_message(chat_id, response)
        except Exception as e:
            print(f"[Error] {e}")
            self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    def send_message(self, chat_id, text):
        """Отправка сообщения в Telegram"""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text[:4000],  # Лимит Telegram
            "parse_mode": "Markdown"
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"[Error sending message] {e}")
    
    def send_chat_action(self, chat_id, action):
        """Отправка статуса typing"""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
        data = {"chat_id": chat_id, "action": action}
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                pass
        except:
            pass
    
    def send_status(self, chat_id):
        """Отправка статуса системы"""
        import subprocess
        
        # Получаем информацию о системе
        hostname = subprocess.getoutput('hostname')
        uptime = subprocess.getoutput('uptime -p')
        df = subprocess.getoutput('df -h / | tail -1')
        
        status_text = (
            f"🖥️ *Prime Status*\n\n"
            f"*Сервер:* `{hostname}`\n"
            f"*Uptime:* {uptime}\n"
            f"*Диск:* `{df}`\n\n"
            f"*Провайдер:* `{DEFAULT_PROVIDER}`\n"
            f"*Модель:* `{DEFAULT_MODEL}`"
        )
        
        self.send_message(chat_id, status_text)
    
    def log_message(self, format, *args):
        """Переопределяем логирование"""
        print(f"[HTTP] {format % args}")


def set_webhook(webhook_url):
    """Установка webhook для бота"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    data = {"url": webhook_url}
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode())
            if result.get('ok'):
                print(f"✅ Webhook установлен: {webhook_url}")
            else:
                print(f"❌ Ошибка установки webhook: {result}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Prime Telegram Bot Server')
    parser.add_argument('--port', type=int, default=8080, help='Порт сервера')
    parser.add_argument('--webhook', type=str, help='URL для webhook (https://...)')
    args = parser.parse_args()
    
    if args.webhook:
        set_webhook(args.webhook)
        return
    
    # Запускаем сервер
    server = HTTPServer(('0.0.0.0', args.port), TelegramHandler)
    print(f"🚀 Prime Telegram Server запущен на порту {args.port}")
    print(f"🤖 Бот: @gpuvpsopenclawbot")
    print(f"📡 Webhook endpoint: http://localhost:{args.port}/webhook")
    print(f"🔧 Провайдер: {DEFAULT_PROVIDER}")
    print("\nДля установки webhook:")
    print(f"  python3 {sys.argv[0]} --webhook https://YOUR_DOMAIN/webhook")
    print("\nНажмите Ctrl+C для остановки")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Сервер остановлен")


if __name__ == "__main__":
    main()
