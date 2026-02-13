from __future__ import annotations

import asyncio
import secrets
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
    parse_request,
)
from app.persistence.database import SessionLocal
from app.services.command_bus import CommandBus
from app.services.event_bus import get_event_bus
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyService,
)

router = APIRouter(tags=["ws"])

connection_manager = ConnectionManager()
event_bus = get_event_bus()

METHOD_SCOPE_MAP = {
    "health.get": "health.read",
    "tasks.list": "tasks.read",
    "tasks.create": "tasks.write",
    "tasks.retry": "tasks.write",
    "bindings.resolve": "routing.read",
    "policy.dm_check": "policy.read",
}

SIDE_EFFECT_METHODS = {"tasks.create", "tasks.retry"}


async def _forward_events(connection_id: str, queue: asyncio.Queue) -> None:
    while True:
        payload = await queue.get()
        message = make_event(event=payload["event"], data=payload["data"])
        await connection_manager.send_json(connection_id, message.model_dump(exclude_none=True))


async def _send_heartbeats(connection_id: str) -> None:
    while True:
        await asyncio.sleep(20)
        message = make_event(event="heartbeat", data={"ok": True})
        await connection_manager.send_json(connection_id, message.model_dump(exclude_none=True))


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket):
    await websocket.accept()

    nonce = secrets.token_urlsafe(24)
    await websocket.send_json(make_challenge(nonce).model_dump())

    try:
        raw_connect = await websocket.receive_json()
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

    connection_id = await connection_manager.add(websocket=websocket, identity=identity)
    subscription_id, queue = await event_bus.subscribe()

    event_forwarder = asyncio.create_task(_forward_events(connection_id=connection_id, queue=queue))
    heartbeat_sender = asyncio.create_task(_send_heartbeats(connection_id=connection_id))

    await connection_manager.send_json(
        connection_id,
        make_event(
            event="presence.connected",
            data={
                "connection_id": connection_id,
                "user_id": str(identity.user_id),
                "username": identity.username,
                "role": identity.role,
            },
        ).model_dump(exclude_none=True),
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
                            make_response(req_id=request.id, result=replay).model_dump(exclude_none=True)
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
                make_response(req_id=request.id, result=result).model_dump(exclude_none=True)
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
        event_forwarder.cancel()
        heartbeat_sender.cancel()
        await event_bus.unsubscribe(subscription_id)
        await connection_manager.remove(connection_id)
