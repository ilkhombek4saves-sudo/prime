# Prime Lite — Quick Start Guide

One-command personal AI agent like OpenClaw. No Docker, no PostgreSQL, just SQLite + local LLM.

## Install

```bash
curl -fsSL https://your-domain.com/install-lite.sh | bash
# Or from repo:
./install-lite.sh
```

## Quick Start

```bash
# 1. Initialize
prime init

# 2. Add your Telegram bot token
nano ~/.config/prime/.env

# 3. Start server
prime serve

# 4. Open dashboard
prime dashboard --open
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `prime init` | Initialize config and database |
| `prime serve` | Start server (http://127.0.0.1:18789) |
| `prime status` | Check all components |
| `prime doctor` | Run diagnostics |
| `prime dashboard` | Show dashboard URL |
| `prime agent "hello"` | Send message to LLM |
| `prime logs` | View logs |
| `prime stop` | Stop daemon |

## Differences from Full Prime

| Feature | Prime Lite | Prime Full |
|---------|------------|------------|
| Database | SQLite (zero-config) | PostgreSQL |
| Frontend | Built-in (no build step) | React SPA |
| Deployment | Single binary | Docker Compose |
| Channels | Telegram only | Telegram, Discord, WebChat |
| UI Port | 18789 (same as API) | 5173 + 8000 |
| Dependencies | Python only | Docker + PostgreSQL |

## Requirements

- Python 3.10+
- Ollama (for local LLM)
- Optional: Telegram bot token

## Security

- All data stored locally in `~/.config/prime/`
- Secrets in `.env` with 600 permissions
- DM pairing required by default
- Localhost-only server (127.0.0.1:18789)

## Troubleshooting

**Ollama not found:**
```bash
curl -fsSL https://ollama.com/install.sh | bash
ollama pull llama3.2
```

**Port in use:**
```bash
prime serve --port 18800
```

**Reset everything:**
```bash
rm -rf ~/.config/prime/
prime init
```
