# Prime — AI Agent Platform

Self-hosted AI agent platform with secure command execution and approval workflows.

## Quick Install

```bash
git clone --depth 1 https://github.com/prime-ai/prime.git
cd prime
./install.sh
```

## Requirements

- Docker & Docker Compose v2
- Git
- 2GB RAM, 10GB disk

## Usage

```bash
prime status    # Check health
prime up        # Start services
prime down      # Stop services
prime logs      # View logs
```

## API

- Health: `http://localhost:8000/api/healthz`
- Docs: `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/api/ws/events`

## License

MIT
