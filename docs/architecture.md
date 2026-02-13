# Architecture

Layers:
- Gateway
- Service
- Plugin
- Persistence
- Admin UI

Execution flow:
1. Gateway validates user and bot access.
2. Plugin resolved and task persisted.
3. Provider executes with retry/rate limit.
4. Result persisted and pushed to UI via WebSocket.
