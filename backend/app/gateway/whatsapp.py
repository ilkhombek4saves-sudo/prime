"""
WhatsApp Gateway — WhatsApp Business API integration.

Supports two modes:
  1. WhatsApp Business API (Cloud API) — official Meta API
     Requires: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN

  2. Twilio WhatsApp — via Twilio sandbox/number
     Requires: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM

Inbound messages are received via webhook at /whatsapp/webhook.
Mount the router in main.py (outside /api prefix) for Meta webhook callbacks.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

WA_API_BASE = "https://graph.facebook.com/v19.0"


class WhatsAppGateway:
    """WhatsApp Business Cloud API gateway."""

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        verify_token: str,
        app_secret: str = "",
    ):
        self.token = token
        self.phone_number_id = phone_number_id
        self.verify_token = verify_token
        self.app_secret = app_secret
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        self._running = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self):
        self._running = True
        logger.info(
            "WhatsApp gateway started (phone_id=%s). Mount /whatsapp/webhook for callbacks.",
            self.phone_number_id,
        )

    async def stop(self):
        self._running = False
        await self._client.aclose()
        logger.info("WhatsApp gateway stopped")

    # ── Webhook verification (GET) ─────────────────────────────────────────────

    def verify_webhook(self, mode: str, token: str, challenge: str) -> str | None:
        """Verify Meta webhook subscription (hub.challenge handshake)."""
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    # ── Payload processing (POST) ──────────────────────────────────────────────

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify X-Hub-Signature-256 header."""
        if not self.app_secret:
            logger.warning("WHATSAPP_APP_SECRET not configured — rejecting unsigned request")
            return False
        expected = "sha256=" + hmac.new(
            self.app_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_webhook(self, body: bytes, headers: dict) -> dict:
        """Process inbound webhook payload from Meta."""
        sig = headers.get("x-hub-signature-256", "")
        if not self.verify_signature(body, sig):
            logger.warning("WhatsApp signature verification failed")
            return {"error": "invalid_signature"}

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"error": "invalid_json"}

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    asyncio.create_task(self._process_message(message, value))

        return {"ok": True}

    async def _process_message(self, message: dict, context: dict):
        msg_type = message.get("type")
        from_number = message.get("from", "")
        msg_id = message.get("id", "")

        # Mark as read
        asyncio.create_task(self._mark_read(msg_id))

        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            # Button/list reply
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive["button_reply"]["title"]
            elif interactive.get("type") == "list_reply":
                text = interactive["list_reply"]["title"]
            else:
                return
        else:
            # Audio, image, etc. — not yet supported
            logger.debug("WhatsApp unsupported message type: %s", msg_type)
            return

        if not text:
            return

        logger.info("WhatsApp message from %s: %s", from_number, text[:80])
        session_id = f"whatsapp-{from_number}"
        response = await self._run_agent(text, session_id=session_id, user_id=from_number)
        if response:
            await self.send_text(from_number, response)

    # ── Agent Integration ──────────────────────────────────────────────────────

    async def _run_agent(self, text: str, session_id: str, user_id: str) -> str:
        try:
            from app.services.agent_runner import AgentRunner
            runner = AgentRunner()
            result = runner.run(text)
            if isinstance(result, str):
                return result
            return result.text if hasattr(result, "text") else str(result)
        except Exception as exc:
            logger.error("WhatsApp agent error: %s", exc)
            return f"Error: {exc}"

    # ── WhatsApp API ───────────────────────────────────────────────────────────

    async def send_text(self, to: str, text: str) -> bool:
        """Send a text message to a WhatsApp number."""
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text[:4096]},
        }
        try:
            resp = await self._client.post(
                f"{WA_API_BASE}/{self.phone_number_id}/messages",
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error("WhatsApp send error: %s %s", resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as exc:
            logger.error("WhatsApp send_text failed: %s", exc)
            return False

    async def _mark_read(self, message_id: str):
        try:
            await self._client.post(
                f"{WA_API_BASE}/{self.phone_number_id}/messages",
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                },
            )
        except (httpx.HTTPError, OSError) as exc:
            logger.debug("Failed to mark WhatsApp message as read: %s", exc)

    async def send_interactive_buttons(
        self, to: str, body: str, buttons: list[dict]
    ) -> bool:
        """Send interactive message with up to 3 quick-reply buttons."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": str(i), "title": b["title"]}}
                        for i, b in enumerate(buttons[:3])
                    ]
                },
            },
        }
        try:
            resp = await self._client.post(
                f"{WA_API_BASE}/{self.phone_number_id}/messages",
                json=payload,
            )
            return resp.status_code < 400
        except Exception as exc:
            logger.error("WhatsApp send_interactive_buttons failed: %s", exc)
            return False


# ── FastAPI webhook router ─────────────────────────────────────────────────────

_gateway_instance: WhatsAppGateway | None = None

webhook_router = APIRouter(tags=["whatsapp-webhook"])


@webhook_router.get("/whatsapp/webhook")
async def whatsapp_verify(request: Request):
    """Meta webhook subscription verification."""
    gw = _gateway_instance
    if not gw:
        return Response("Gateway not configured", status_code=503)
    params = dict(request.query_params)
    challenge = gw.verify_webhook(
        mode=params.get("hub.mode", ""),
        token=params.get("hub.verify_token", ""),
        challenge=params.get("hub.challenge", ""),
    )
    if challenge is not None:
        return Response(challenge)
    return Response("Forbidden", status_code=403)


@webhook_router.post("/whatsapp/webhook")
async def whatsapp_receive(request: Request):
    """Receive inbound WhatsApp events."""
    gw = _gateway_instance
    if not gw:
        return {"error": "gateway_not_configured"}
    body = await request.body()
    headers = dict(request.headers)
    result = await gw.handle_webhook(body, headers)
    return result


# ── Factory ────────────────────────────────────────────────────────────────────

def build_whatsapp_gateway() -> WhatsAppGateway | None:
    """Build WhatsApp gateway from environment variables."""
    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_ID", "").strip()
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "prime-webhook").strip()
    if not token or not phone_id:
        return None

    gw = WhatsAppGateway(
        token=token,
        phone_number_id=phone_id,
        verify_token=verify_token,
        app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
    )
    global _gateway_instance
    _gateway_instance = gw
    return gw
