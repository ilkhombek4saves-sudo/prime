from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket

from app.gateway.auth_ws import WSIdentity


@dataclass
class ConnectionState:
    connection_id: str
    websocket: WebSocket
    identity: WSIdentity
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, ConnectionState] = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket: WebSocket, identity: WSIdentity) -> str:
        connection_id = str(uuid.uuid4())
        state = ConnectionState(connection_id=connection_id, websocket=websocket, identity=identity)
        async with self._lock:
            self._connections[connection_id] = state
        return connection_id

    async def remove(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def get(self, connection_id: str) -> ConnectionState | None:
        async with self._lock:
            return self._connections.get(connection_id)

    async def send_json(self, connection_id: str, payload: dict) -> None:
        state = await self.get(connection_id)
        if state is None:
            return
        await state.websocket.send_json(payload)

    async def broadcast_json(self, payload: dict) -> None:
        async with self._lock:
            connection_ids = list(self._connections.keys())
        for connection_id in connection_ids:
            await self.send_json(connection_id, payload)
