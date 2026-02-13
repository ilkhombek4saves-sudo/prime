# API Summary

Base prefix: `/api`

- `POST /auth/login`
- `GET/POST/PUT/DELETE /bots`
- `GET/POST/PUT/DELETE /agents`
- `GET/POST/PUT/DELETE /bindings`, `GET /bindings/resolve`
- `GET/POST /pairing/requests`, `POST /pairing/requests/{id}/approve`, `POST /pairing/requests/{id}/reject`
- `GET /pairing/devices`, `POST /pairing/devices/{device_id}/revoke`
- `GET/POST/PUT/DELETE /providers`
- `GET/POST/PUT/DELETE /plugins`
- `GET /sessions`, `GET /sessions/{id}`
- `GET/POST /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/retry`
- `GET/POST /users`, `POST /users/{id}/reset-token`
- `GET /settings`, `POST /settings/import-config`
- `GET /healthz`, `GET /metrics`
- `WS /ws/events`
