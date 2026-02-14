"""
Webhooks API — admin CRUD for webhook bindings + public inbound receiver.

Admin (auth required, mounted under /api):
  GET    /api/webhooks        — list bindings
  POST   /api/webhooks        — create binding
  DELETE /api/webhooks/{id}   — delete binding

Public (no auth — HMAC-protected, mounted at root):
  POST   /hooks/{path}        — receive webhook, trigger agent
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.persistence.models import User

# Admin CRUD router — included under /api in router.py
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Public inbound receiver — mounted directly on app root in main.py
public_router = APIRouter(tags=["webhooks-public"])


class WebhookCreate(BaseModel):
    name: str
    path: str
    message_template: str
    agent_id: str | None = None
    secret: str | None = None


class WebhookResponse(BaseModel):
    id: str
    name: str
    path: str
    agent_id: str | None = None
    active: bool
    created_at: str


def _run(coro):
    """Run async coro from sync FastAPI endpoint."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)
        return loop.run_until_complete(coro)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Admin CRUD ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WebhookResponse])
def list_webhooks(current_user: User = Depends(get_current_user)):
    from app.services.webhook_service import WebhookService
    bindings = _run(WebhookService.list_bindings())
    return [WebhookResponse(**b) for b in bindings]


@router.post("", response_model=WebhookResponse, status_code=201)
def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
):
    from app.services.webhook_service import WebhookService
    binding = _run(
        WebhookService.register(
            name=body.name,
            path=body.path,
            message_template=body.message_template,
            agent_id=body.agent_id,
            secret=body.secret,
        )
    )
    return WebhookResponse(**binding)


@router.delete("/{webhook_id}", status_code=204)
def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    from app.services.webhook_service import WebhookService
    ok = _run(WebhookService.unregister(str(webhook_id)))
    if not ok:
        raise HTTPException(status_code=404, detail="Webhook binding not found")


# ── Public inbound receiver ────────────────────────────────────────────────────

@public_router.post("/hooks/{path:path}", include_in_schema=True, tags=["webhooks-public"])
async def receive_webhook(path: str, request: Request):
    """
    Public endpoint — receives incoming webhooks and triggers the bound agent.
    No authentication required; use HMAC secret for security.
    """
    from app.services.webhook_service import WebhookService

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    headers = dict(request.headers)
    result = await WebhookService.process(f"/{path}", payload, headers)
    return {"status": "ok", "message": result}
