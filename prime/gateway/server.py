"""
Prime Gateway — Central control plane (FastAPI)
Handles routing from all channels (Telegram, Discord, WebChat, CLI)
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from prime.config.settings import settings
from prime.core.agent import Agent, get_system_info


# ─── Active WebSocket connections (for WebChat) ───────────────────────────────
_ws_connections: dict[str, "WebSocket"] = {}


@asynccontextmanager
async def lifespan(app):
    print(f"  → Gateway starting on {settings.GATEWAY_HOST}:{settings.GATEWAY_PORT}")
    yield
    print("  → Gateway stopped")


def create_app() -> "FastAPI":
    if not HAS_FASTAPI:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="Prime Gateway",
        description="AI Agent Control Plane",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Dashboard ─────────────────────────────────────────────────────────
    from prime.dashboard.app import mount_dashboard
    mount_dashboard(app)

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "2.0.0", "time": datetime.now().isoformat()}

    @app.get("/status")
    async def status():
        info = get_system_info()
        try:
            from prime.core.memory import get_db
            stats = get_db().stats()
        except Exception:
            stats = {}
        return {
            "status": "running",
            "provider": settings.best_provider(),
            "providers_available": settings.available_providers(),
            "system": info,
            "db_stats": stats,
        }

    # ── Chat API (REST) ────────────────────────────────────────────────────
    @app.post("/chat")
    async def chat(request: Request):
        body = await request.json()
        message = body.get("message", "").strip()
        session_id = body.get("session_id", f"api-{uuid.uuid4().hex[:8]}")
        provider = body.get("provider")
        model = body.get("model")
        user_id = body.get("user_id")

        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        agent = Agent(
            session_id=session_id,
            provider=provider,
            model=model,
            channel="api",
            user_id=user_id,
        )
        response = await asyncio.to_thread(agent.chat, message)
        return {"response": response, "session_id": session_id}

    # ── WebSocket (WebChat) ────────────────────────────────────────────────
    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        await websocket.accept()
        _ws_connections[session_id] = websocket
        agent = Agent(session_id=session_id, channel="webchat")

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                user_message = msg.get("message", "")
                if not user_message:
                    continue

                # Stream: send "thinking" status
                await websocket.send_text(json.dumps({"type": "status", "content": "thinking"}))

                response = await asyncio.to_thread(agent.chat, user_message)
                await websocket.send_text(json.dumps({"type": "message", "content": response}))

        except WebSocketDisconnect:
            pass
        finally:
            _ws_connections.pop(session_id, None)

    # ── Telegram Webhook ───────────────────────────────────────────────────
    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        data = await request.json()
        asyncio.create_task(_handle_telegram_update(data))
        return {"ok": True}

    # ── Memory API ─────────────────────────────────────────────────────────
    @app.get("/api/memories")
    async def list_memories(user_id: str = None):
        try:
            from prime.core.memory import get_db
            return get_db().list_memories(user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/memories")
    async def save_memory(request: Request):
        body = await request.json()
        from prime.core.memory import get_db
        get_db().save_memory(body["key"], body["content"], body.get("user_id"))
        return {"ok": True}

    @app.delete("/api/memories/{key}")
    async def delete_memory(key: str, user_id: str = None):
        from prime.core.memory import get_db
        db = get_db()
        with db._conn() as conn:
            conn.execute(
                "DELETE FROM memories WHERE key = ? AND user_id IS ?", (key, user_id)
            )
        return {"ok": True}

    # ── Sessions API ────────────────────────────────────────────────────────
    @app.get("/api/sessions")
    async def list_sessions(channel: str = None):
        from prime.core.memory import get_db
        return get_db().list_sessions(channel)

    @app.get("/api/sessions/{session_id}/messages")
    async def get_messages(session_id: str, limit: int = 50):
        from prime.core.memory import get_db
        return get_db().get_messages(session_id, limit)

    # ── Tasks API ───────────────────────────────────────────────────────────
    @app.get("/api/tasks")
    async def list_tasks():
        from prime.core.memory import get_db
        return get_db().list_tasks()

    @app.post("/api/tasks")
    async def create_task(request: Request):
        body = await request.json()
        from prime.core.memory import get_db
        task_id = get_db().save_task(body["name"], body["schedule"], body["command"])
        return {"ok": True, "id": task_id}

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: int):
        from prime.core.memory import get_db
        get_db().delete_task(task_id)
        return {"ok": True}

    return app


# ─── Telegram handler ─────────────────────────────────────────────────────────
async def _handle_telegram_update(data: dict):
    """Process incoming Telegram update asynchronously."""
    try:
        from prime.integrations.telegram import handle_update
        await handle_update(data)
    except Exception as e:
        print(f"  ✗ Telegram handler error: {e}")


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn")
        return

    app = create_app()
    uvicorn.run(
        app,
        host=settings.GATEWAY_HOST,
        port=settings.GATEWAY_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
