"""
Slack Gateway — inbound Events API + outbound message posting.

Configuration (env vars):
  SLACK_BOT_TOKEN   — xoxb-... bot OAuth token
  SLACK_APP_TOKEN   — xapp-... app-level token (Socket Mode)
  SLACK_SIGNING_SECRET — request signature verification secret

The gateway uses Socket Mode (preferred) when SLACK_APP_TOKEN is set,
otherwise falls back to an HTTP Events endpoint at /slack/events.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


class SlackGateway:
    """
    Slack gateway that listens for events and dispatches to an agent runner.

    Supports two modes:
      - Socket Mode (SLACK_APP_TOKEN set): persistent WSS connection, no public URL needed
      - HTTP Events API (fallback): POST /slack/events endpoint
    """

    def __init__(
        self,
        bot_token: str,
        signing_secret: str = "",
        app_token: str = "",
        agent_runner_factory: Callable | None = None,
    ):
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.app_token = app_token
        self._agent_runner_factory = agent_runner_factory
        self._client = httpx.AsyncClient(
            base_url=SLACK_API,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=30,
        )
        self._socket_task: asyncio.Task | None = None
        self._running = False
        self._bot_id: str | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self):
        self._running = True
        # Resolve own bot_id to avoid self-echo
        try:
            resp = await self._client.get("/auth.test")
            data = resp.json()
            if data.get("ok"):
                self._bot_id = data.get("bot_id")
                logger.info("Slack gateway authenticated as %s", data.get("user"))
        except Exception as exc:
            logger.warning("Slack auth.test failed: %s", exc)

        if self.app_token:
            self._socket_task = asyncio.create_task(self._socket_mode_loop())
            logger.info("Slack Socket Mode started")
        else:
            logger.info("Slack gateway ready (HTTP Events API mode — mount /slack/events)")

    async def stop(self):
        self._running = False
        if self._socket_task:
            self._socket_task.cancel()
            try:
                await self._socket_task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
        logger.info("Slack gateway stopped")

    # ── Socket Mode ────────────────────────────────────────────────────────────

    async def _socket_mode_loop(self):
        """Connect to Slack Socket Mode WSS and process events."""
        import websockets

        while self._running:
            try:
                url = await self._get_socket_url()
                if not url:
                    await asyncio.sleep(30)
                    continue

                async with websockets.connect(url, ping_interval=30) as ws:
                    logger.info("Slack Socket Mode connected")
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            await self._handle_socket_message(ws, msg)
                        except Exception as exc:
                            logger.warning("Slack socket message error: %s", exc)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Slack socket disconnected: %s — reconnecting in 10s", exc)
                await asyncio.sleep(10)

    async def _get_socket_url(self) -> str | None:
        try:
            resp = await httpx.AsyncClient(timeout=10).post(
                f"{SLACK_API}/apps.connections.open",
                headers={"Authorization": f"Bearer {self.app_token}"},
            )
            data = resp.json()
            if data.get("ok"):
                return data["url"]
            logger.error("Slack apps.connections.open failed: %s", data.get("error"))
        except Exception as exc:
            logger.error("Slack socket URL fetch error: %s", exc)
        return None

    async def _handle_socket_message(self, ws, msg: dict):
        # Acknowledge immediately
        if "envelope_id" in msg:
            await ws.send(json.dumps({"envelope_id": msg["envelope_id"]}))

        msg_type = msg.get("type")
        if msg_type == "events_api":
            payload = msg.get("payload", {})
            await self._dispatch_event(payload.get("event", {}))
        elif msg_type == "slash_commands":
            payload = msg.get("payload", {})
            await self._dispatch_slash(payload)

    # ── HTTP Events API ────────────────────────────────────────────────────────

    def verify_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        """Verify Slack request signature (HMAC-SHA256)."""
        if not self.signing_secret:
            logger.warning("SLACK_SIGNING_SECRET not configured — rejecting unsigned request")
            return False
        basestring = f"v0:{timestamp}:{body.decode()}".encode()
        expected = "v0=" + hmac.new(
            self.signing_secret.encode(), basestring, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_http_event(self, body: bytes, headers: dict) -> dict:
        """Handle an inbound HTTP event from Slack Events API."""
        # Replay attack protection
        ts = headers.get("x-slack-request-timestamp", "")
        if ts and abs(time.time() - int(ts)) > 300:
            return {"error": "stale_request"}

        sig = headers.get("x-slack-signature", "")
        if not self.verify_signature(body, ts, sig):
            return {"error": "invalid_signature"}

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"error": "invalid_json"}

        # URL verification challenge
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}

        event = payload.get("event", {})
        asyncio.create_task(self._dispatch_event(event))
        return {"ok": True}

    # ── Event Dispatch ─────────────────────────────────────────────────────────

    async def _dispatch_event(self, event: dict):
        event_type = event.get("type")
        if event_type not in ("message", "app_mention"):
            return

        # Ignore bot messages (avoid self-echo)
        if event.get("bot_id") == self._bot_id:
            return
        if event.get("subtype"):  # message_changed, etc.
            return

        text = event.get("text", "").strip()
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        user = event.get("user", "slack_user")

        if not text or not channel:
            return

        # Strip @bot mention prefix
        if text.startswith("<@"):
            text = text.split(">", 1)[-1].strip()

        logger.info("Slack message from %s in %s: %s", user, channel, text[:80])
        response = await self._run_agent(text, session_id=f"slack-{channel}-{user}", user_id=user)
        if response:
            await self.post_message(channel, response, thread_ts=thread_ts)

    async def _dispatch_slash(self, payload: dict):
        text = payload.get("text", "").strip()
        channel = payload.get("channel_id", "")
        user = payload.get("user_id", "slack_user")
        response_url = payload.get("response_url", "")

        if not text:
            text = "help"

        response = await self._run_agent(text, session_id=f"slack-slash-{user}", user_id=user)
        if response and response_url:
            async with httpx.AsyncClient() as c:
                await c.post(response_url, json={"text": response, "response_type": "ephemeral"})

    # ── Agent Integration ──────────────────────────────────────────────────────

    async def _run_agent(self, text: str, session_id: str, user_id: str) -> str:
        """Run agent and return response text."""
        if self._agent_runner_factory:
            try:
                return await self._agent_runner_factory(text, session_id=session_id, user_id=user_id)
            except Exception as exc:
                logger.error("Slack agent error: %s", exc)
                return f"Error: {exc}"

        # Default: use backend AgentRunner
        try:
            from app.services.agent_runner import AgentRunner
            runner = AgentRunner()
            result = runner.run(text)
            if isinstance(result, str):
                return result
            return result.text if hasattr(result, "text") else str(result)
        except Exception as exc:
            logger.error("Slack agent runner error: %s", exc)
            return f"Error processing request: {exc}"

    # ── Slack API ──────────────────────────────────────────────────────────────

    async def post_message(self, channel: str, text: str, thread_ts: str | None = None) -> bool:
        """Post a message to a Slack channel."""
        payload = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        try:
            resp = await self._client.post("/chat.postMessage", json=payload)
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack post error: %s", data.get("error"))
                return False
            return True
        except Exception as exc:
            logger.error("Slack post_message failed: %s", exc)
            return False


_gateway_instance: SlackGateway | None = None


def build_slack_gateway() -> SlackGateway | None:
    """Build Slack gateway from environment variables. Returns None if not configured."""
    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    if not bot_token:
        return None
    gw = SlackGateway(
        bot_token=bot_token,
        signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        app_token=os.getenv("SLACK_APP_TOKEN", ""),
    )
    global _gateway_instance
    _gateway_instance = gw
    return gw
