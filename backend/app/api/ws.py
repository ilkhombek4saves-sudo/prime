from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.gateway.auth_ws import authenticate_connect, require_scope
from app.gateway.connection_manager import ConnectionManager
from app.gateway.protocol import (
    ProtocolError,
    make_challenge,
    make_error,
    make_event,
    make_response,
    parse_connect,
    parse_connect_request,
    parse_request,
    utc_now_ms,
    PROTOCOL_VERSION,
)
from app.config.settings import get_settings
from app.persistence.database import SessionLocal
from app.services.command_bus import CommandBus
from app.services.config_service import config_hash
from app.services.event_bus import get_event_bus
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyService,
)

router = APIRouter(tags=["ws"])

connection_manager = ConnectionManager()
event_bus = get_event_bus()
SERVER_START_MS = utc_now_ms()
connection_seq: dict[str, int] = {}
presence_state_version = 0
_LOCAL_WS_CLIENT_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient", "testserver"}


def _is_local_ws_client(settings, client_host: str) -> bool:
    if client_host in _LOCAL_WS_CLIENT_HOSTS:
        return True
    # In docker-compose dev mode, the host often appears as a private bridge IP (e.g. 172.17.0.1).
    # Treat private RFC1918 clients as "local" only outside production to keep prod strict.
    if getattr(settings, "app_env", "dev") == "prod":
        return False
    try:
        ip = ipaddress.ip_address(client_host)
    except Exception:
        return False
    return bool(ip.is_private or ip.is_loopback)


def _config_hash() -> str:
    return config_hash("config")

METHOD_SCOPE_MAP = {
    "health.get": "health.read",
    "health": "health.read",
    "status": "status.read",
    "system-presence": "system.read",
    "system-event": "system.write",
    "config.get": "config.read",
    "config.schema": "config.read",
    "tasks.list": "tasks.read",
    "tasks.create": "tasks.write",
    "tasks.retry": "tasks.write",
    "bindings.resolve": "routing.read",
    "policy.dm_check": "policy.read",
}

SIDE_EFFECT_METHODS = {"tasks.create", "tasks.retry"}


def _next_seq(connection_id: str) -> int:
    current = connection_seq.get(connection_id, 0) + 1
    connection_seq[connection_id] = current
    return current


async def _send_event(
    connection_id: str,
    event: str,
    payload: dict[str, Any],
    *,
    state_version: int | None = None,
) -> None:
    message = make_event(event=event, payload=payload, seq=_next_seq(connection_id))
    if state_version is not None:
        message.state_version = state_version
    await connection_manager.send_json(connection_id, message.model_dump(exclude_none=True, by_alias=True))


async def _forward_events(connection_id: str, queue: asyncio.Queue) -> None:
    while True:
        payload = await queue.get()
        data = payload.get("data") or payload.get("payload") or {}
        await _send_event(connection_id, payload["event"], data)


async def _send_heartbeats(connection_id: str) -> None:
    while True:
        await asyncio.sleep(20)
        await _send_event(connection_id, "heartbeat", {"ok": True})


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket):
    await websocket.accept()

    global presence_state_version
    settings = get_settings()
    client_host = getattr(websocket.client, "host", "") if websocket.client else ""
    if not settings.ws_allow_remote and not _is_local_ws_client(settings, client_host):
        await websocket.send_json(
            make_error(
                code="forbidden",
                message="remote websocket connections are disabled",
            ).model_dump(exclude_none=True)
        )
        await websocket.close(code=1008)
        return
    if settings.allow_forwarded_headers:
        forwarded = any(
            key in websocket.headers
            for key in ("x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "forwarded")
        )
        if forwarded and not _is_local_ws_client(settings, client_host):
            await websocket.send_json(
                make_error(
                    code="forbidden",
                    message="untrusted proxy headers",
                ).model_dump(exclude_none=True)
            )
            await websocket.close(code=1008)
            return
    nonce = secrets.token_urlsafe(24)
    await websocket.send_json(make_challenge(nonce).model_dump(exclude_none=True, by_alias=True))

    try:
        raw_connect = await websocket.receive_json()
        connect_request = None
        connect_req_id = None
        if raw_connect.get("type") == "req" and raw_connect.get("method") == "connect":
            connect_request = parse_connect_request(raw_connect)
            connect_req_id = raw_connect.get("id")
            identity = authenticate_connect(connect_request, expected_nonce=nonce)
            min_p = connect_request.min_protocol or settings.ws_protocol_min
            max_p = connect_request.max_protocol or settings.ws_protocol_max
            if not (min_p <= PROTOCOL_VERSION <= max_p):
                raise ProtocolError(
                    code="protocol_mismatch",
                    message=f"Server protocol {PROTOCOL_VERSION} not in [{min_p}, {max_p}]",
                )
        else:
            if settings.ws_strict_connect:
                raise ProtocolError(code="connect_required", message="connect request required")
            connect_message = parse_connect(raw_connect)
            identity = authenticate_connect(connect_message, expected_nonce=nonce)
    except Exception as exc:
        code = "auth_failed"
        message = "WebSocket authentication failed"
        if isinstance(exc, ProtocolError):
            code = exc.code
            message = exc.message
        await websocket.send_json(make_error(code=code, message=message).model_dump(exclude_none=True))
        await websocket.close(code=1008)
        return

    client_info = {}
    device_info = {}
    caps = []
    commands = []
    permissions = []
    if connect_request is not None:
        client_info = connect_request.client.model_dump(by_alias=True)
        device_info = connect_request.device.model_dump(by_alias=True) if connect_request.device else {}
        caps = connect_request.caps or []
        commands = connect_request.commands or []
        permissions = connect_request.permissions or []

    connection_id = await connection_manager.add(
        websocket=websocket,
        identity=identity,
        client_info=client_info,
        device_info=device_info,
        caps=caps,
        commands=commands,
        permissions=permissions,
    )
    connection_seq[connection_id] = 0
    subscription_id, queue = await event_bus.subscribe()

    event_forwarder = asyncio.create_task(_forward_events(connection_id=connection_id, queue=queue))
    heartbeat_sender = asyncio.create_task(_send_heartbeats(connection_id=connection_id))

    if connect_req_id:
        snapshot_presence = await connection_manager.presence_list()
        await connection_manager.send_json(
            connection_id,
            make_response(
                req_id=connect_req_id,
                payload={
                    "hello": "ok",
                    "protocol": PROTOCOL_VERSION,
                    "serverTime": utc_now_ms(),
                    "connectionId": connection_id,
                    "uptimeMs": utc_now_ms() - SERVER_START_MS,
                    "server": {
                        "version": settings.app_version,
                        "commit": settings.app_commit,
                        "host": None,
                        "connId": connection_id,
                    },
                    "features": {
                        "methods": sorted(METHOD_SCOPE_MAP.keys()),
                        "events": [
                            "presence.connected",
                            "presence.disconnected",
                            "heartbeat",
                            "task.updated",
                            "task.started",
                            "task.completed",
                            "task.failed",
                            "stream.start",
                            "stream.chunk",
                            "stream.end",
                            "stream.error",
                        ],
                    },
                    "snapshot": {
                        "presence": snapshot_presence,
                        "health": {"status": "ok"},
                        "configHash": _config_hash(),
                        "stateVersion": presence_state_version,
                    },
                    "policy": {
                        "maxPayload": settings.ws_max_payload_bytes,
                        "maxBufferedBytes": settings.ws_max_buffered_bytes,
                        "tickIntervalMs": settings.ws_tick_interval_ms,
                    },
                    "auth": {
                        "deviceToken": None,
                        "role": identity.role,
                        "scopes": sorted(identity.scopes),
                    },
                    "user": {
                        "id": str(identity.user_id),
                        "username": identity.username,
                        "role": identity.role,
                        "scopes": sorted(identity.scopes),
                    },
                },
            ).model_dump(exclude_none=True, by_alias=True),
        )

    presence_state_version += 1
    await _send_event(
        connection_id,
        "presence.connected",
        {
            "connection_id": connection_id,
            "user_id": str(identity.user_id),
            "username": identity.username,
            "role": identity.role,
        },
        state_version=presence_state_version,
    )

    try:
        while True:
            raw_message: dict[str, Any] = await websocket.receive_json()

            try:
                request = parse_request(raw_message)
            except ProtocolError as exc:
                await websocket.send_json(
                    make_error(code=exc.code, message=exc.message).model_dump(exclude_none=True)
                )
                continue

            await connection_manager.touch(connection_id)

            if request.method == "system-presence":
                presence = await connection_manager.presence_list()
                await websocket.send_json(
                    make_response(req_id=request.id, payload={"presence": presence}).model_dump(
                        exclude_none=True, by_alias=True
                    )
                )
                continue

            if request.method == "system-event":
                if identity.role != "admin":
                    await websocket.send_json(
                        make_error(
                            code="forbidden",
                            message="admin role required",
                            req_id=request.id,
                        ).model_dump(exclude_none=True)
                    )
                    continue
                event = str(request.params.get("event", "system.event"))
                data = request.params.get("payload") or request.params.get("data") or {}
                event_bus.publish_nowait(event, data)
                await websocket.send_json(
                    make_response(req_id=request.id, payload={"ok": True}).model_dump(
                        exclude_none=True, by_alias=True
                    )
                )
                continue

            required_scope = METHOD_SCOPE_MAP.get(request.method)
            if required_scope:
                try:
                    require_scope(identity, required_scope)
                except ProtocolError as exc:
                    await websocket.send_json(
                        make_error(code=exc.code, message=exc.message, req_id=request.id).model_dump(
                            exclude_none=True
                        )
                    )
                    continue

            idempotency_key = request.idempotency_key
            with SessionLocal() as db:
                idempotency_service = IdempotencyService(db)
                command_bus = CommandBus(db)

                if request.method in SIDE_EFFECT_METHODS and not idempotency_key:
                    await websocket.send_json(
                        make_error(
                            code="idempotency_required",
                            message="idempotency_key is required for side-effect methods",
                            req_id=request.id,
                        ).model_dump(exclude_none=True)
                    )
                    continue

                if request.method in SIDE_EFFECT_METHODS and idempotency_key:
                    try:
                        replay = idempotency_service.reserve_or_get(
                            key=idempotency_key,
                            actor_id=identity.user_id,
                            method=request.method,
                            payload=request.params,
                        )
                    except IdempotencyConflictError as exc:
                        await websocket.send_json(
                            make_error(
                                code="idempotency_conflict",
                                message=str(exc),
                                req_id=request.id,
                            ).model_dump(exclude_none=True)
                        )
                        continue
                    except IdempotencyInProgressError as exc:
                        await websocket.send_json(
                            make_error(
                                code="idempotency_in_progress",
                                message=str(exc),
                                req_id=request.id,
                            ).model_dump(exclude_none=True)
                        )
                        continue

                    if replay is not None:
                        await websocket.send_json(
                            make_response(req_id=request.id, payload=replay).model_dump(exclude_none=True, by_alias=True)
                        )
                        continue

                try:
                    result = command_bus.dispatch(
                        method=request.method,
                        params=request.params,
                        user_claims={
                            "sub": str(identity.user_id),
                            "username": identity.username,
                            "role": identity.role,
                        },
                    )
                except ValueError as exc:
                    if idempotency_key:
                        idempotency_service.fail(idempotency_key, str(exc))
                    await websocket.send_json(
                        make_error(
                            code="command_failed",
                            message=str(exc),
                            req_id=request.id,
                        ).model_dump(exclude_none=True)
                    )
                    continue

                if idempotency_key:
                    idempotency_service.complete(idempotency_key, result)

            await websocket.send_json(
                make_response(req_id=request.id, payload=result).model_dump(exclude_none=True, by_alias=True)
            )

            if request.method.startswith("tasks."):
                event_bus.publish_nowait(
                    "task.updated",
                    {
                        "method": request.method,
                        "request_id": request.id,
                        "actor": identity.username,
                    },
                )

    except WebSocketDisconnect:
        pass
    finally:
        try:
            presence_state_version += 1
            await _send_event(
                connection_id,
                "presence.disconnected",
                {
                    "connection_id": connection_id,
                    "user_id": str(identity.user_id),
                    "username": identity.username,
                    "role": identity.role,
                },
                state_version=presence_state_version,
            )
        except Exception:
            pass
        event_forwarder.cancel()
        heartbeat_sender.cancel()
        await event_bus.unsubscribe(subscription_id)
        await connection_manager.remove(connection_id)
        connection_seq.pop(connection_id, None)
