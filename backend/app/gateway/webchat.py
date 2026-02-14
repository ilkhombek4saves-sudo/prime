"""
WebChat gateway — REST/WebSocket-based chat for embedding in web pages.
Provides /api/chat/send and /ws/chat/{session_id} endpoints.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.gateway.base import GatewayAdapter
from app.persistence.database import SessionLocal
from app.persistence.models import (
    Agent, Bot, Provider, Session, SessionStatus, User, UserRole,
)
from app.services.agent_runner import AgentRunner
from app.services.binding_resolver import BindingResolver
from app.services.event_bus import get_event_bus
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["webchat"])

_memory_svc = MemoryService()
_agent_runner = AgentRunner()
_active_ws: dict[str, WebSocket] = {}


class ChatRequest(BaseModel):
    bot_name: str
    session_token: str | None = None
    message: str
    user_name: str = "web_user"


class ChatResponse(BaseModel):
    session_token: str
    reply: str
    agent: str
    model: str | None = None


@router.post("/send", response_model=ChatResponse)
async def chat_send(req: ChatRequest):
    loop = asyncio.get_running_loop()

    with SessionLocal() as db:
        bot_record = db.query(Bot).filter(Bot.name == req.bot_name, Bot.active.is_(True)).first()
        if not bot_record:
            return ChatResponse(session_token="", reply="Bot not found.", agent="system")

        resolver = BindingResolver(db)
        binding = resolver.resolve(
            channel="webchat",
            account_id=str(bot_record.id),
            peer=req.session_token or "new",
            bot_id=bot_record.id,
        )
        if not binding:
            return ChatResponse(session_token="", reply="No agent binding.", agent="system")

        agent = db.get(Agent, binding.agent_id)
        if not agent or not agent.active:
            return ChatResponse(session_token="", reply="Agent unavailable.", agent="system")

        user = db.query(User).filter(User.username == req.user_name).first()
        if not user:
            user = User(username=req.user_name, role=UserRole.user)
            db.add(user)
            db.commit()
            db.refresh(user)

        session_token = req.session_token or uuid.uuid4().hex
        session = (
            db.query(Session)
            .filter(
                Session.bot_id == bot_record.id,
                Session.user_id == user.id,
                Session.agent_id == agent.id,
                Session.status == SessionStatus.active,
            )
            .first()
        )
        if not session:
            session = Session(
                bot_id=bot_record.id, user_id=user.id,
                agent_id=agent.id, provider_id=agent.default_provider_id,
                status=SessionStatus.active,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        provider = db.get(Provider, agent.default_provider_id) if agent.default_provider_id else None
        if not provider or not provider.active:
            return ChatResponse(session_token=session_token, reply="Provider not configured.", agent=agent.name)

        history = []
        if agent.memory_enabled:
            history = _memory_svc.get_history(db, session.id, agent.max_history_messages)

        ptype = provider.type
        pname = provider.name
        pconfig = dict(provider.config)
        sys_prompt = agent.system_prompt
        agent_name = agent.name
        sid = session.id

    result = await loop.run_in_executor(
        None,
        lambda: _agent_runner.run_with_meta(
            req.message,
            provider_type=ptype,
            provider_name=pname,
            provider_config=pconfig,
            system=sys_prompt,
            history=history,
        ),
    )

    with SessionLocal() as db:
        _memory_svc.save_exchange(db, sid, req.message, result.text)

    get_event_bus().publish_nowait(
        "task.webchat_message",
        {"bot": req.bot_name, "agent": agent_name},
    )

    return ChatResponse(
        session_token=session_token,
        reply=result.text,
        agent=agent_name,
        model=result.model,
    )


@router.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    _active_ws[session_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "invalid JSON"})
                continue

            req = ChatRequest(
                bot_name=msg.get("bot_name", "default"),
                session_token=session_id,
                message=msg.get("message", ""),
                user_name=msg.get("user_name", "ws_user"),
            )
            resp = await chat_send(req)
            await websocket.send_json(resp.model_dump())
    except WebSocketDisconnect:
        pass
    finally:
        _active_ws.pop(session_id, None)


class WebChatGateway(GatewayAdapter):
    async def start(self) -> None:
        logger.info("WebChat gateway ready (endpoints registered)")

    async def stop(self) -> None:
        for ws in list(_active_ws.values()):
            try:
                await ws.close()
            except Exception as exc:
                logger.debug("Error closing WebChat WS: %s", exc)
        _active_ws.clear()
