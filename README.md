# Prime — AI Agent Platform

Self-hosted AI agent platform with secure command execution and approval workflows.

## Quick Start

### 1. Скачай проект

```bash
# Способ 1: Git
git clone https://github.com/prime-ai/prime.git
cd prime

# Способ 2: Скачай архив
wget https://github.com/prime-ai/prime/archive/refs/heads/main.zip
unzip main.zip
cd prime-main

# Способ 3: Просто скопируй папку
```

### 2. Запусти установку

```bash
./install.sh
```

Это создаст `.env`, настроит CLI команду `prime` и запустит сервисы.

### 3. Готово!

```bash
prime status    # Проверить статус
prime up        # Запустить (если остановлен)
prime down      # Остановить
prime logs      # Посмотреть логи
```

## API

- **Health**: http://localhost:8000/api/healthz
- **Docs**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/api/ws/events

## Requirements

- Docker & Docker Compose v2
- 2GB RAM, 10GB disk

## Features

- 🤖 **AI Agents** — Multi-provider LLM support
- 🔒 **Secure Execution** — Risk-based approval workflow
- 💬 **Multi-Channel** — Telegram, Discord, Slack, WhatsApp
- 🌐 **WebSocket Control Plane** — Real-time protocol
- 📊 **Cost Tracking** — Per-agent analytics

## License

MIT
