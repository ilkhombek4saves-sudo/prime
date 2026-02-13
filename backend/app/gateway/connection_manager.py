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
    client_info: dict = field(default_factory=dict)
    device_info: dict = field(default_factory=dict)
    caps: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_input_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def presence_entry(self) -> dict:
        now = datetime.now(timezone.utc)
        last_input_seconds = max(0, int((now - self.last_input_at).total_seconds()))
        client = self.client_info or {}
        return {
            "connectionId": self.connection_id,
            "userId": str(self.identity.user_id),
            "username": self.identity.username,
            "role": self.identity.role,
            "host": getattr(self.websocket.client, "host", None),
            "ip": getattr(self.websocket.client, "host", None),
            "version": client.get("version"),
            "platform": client.get("platform"),
            "deviceFamily": client.get("deviceFamily"),
            "modelIdentifier": client.get("modelIdentifier"),
            "mode": client.get("mode"),
            "instanceId": client.get("instanceId"),
            "lastInputSeconds": last_input_seconds,
            "ts": now.isoformat(),
            "caps": self.caps,
            "commands": self.commands,
            "permissions": self.permissions,
        }


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, ConnectionState] = {}
        self._lock = asyncio.Lock()

    async def add(
        self,
        websocket: WebSocket,
        identity: WSIdentity,
        *,
        client_info: dict | None = None,
        device_info: dict | None = None,
        caps: list[str] | None = None,
        commands: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> str:
        connection_id = str(uuid.uuid4())
        state = ConnectionState(
            connection_id=connection_id,
            websocket=websocket,
            identity=identity,
            client_info=client_info or {},
            device_info=device_info or {},
            caps=caps or [],
            commands=commands or [],
            permissions=permissions or [],
        )
        async with self._lock:
            self._connections[connection_id] = state
        return connection_id

    async def remove(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def get(self, connection_id: str) -> ConnectionState | None:
        async with self._lock:
            return self._connections.get(connection_id)

    async def touch(self, connection_id: str) -> None:
        async with self._lock:
            state = self._connections.get(connection_id)
            if state:
                state.last_input_at = datetime.now(timezone.utc)

    async def presence_list(self) -> list[dict]:
        async with self._lock:
            return [state.presence_entry() for state in self._connections.values()]

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
