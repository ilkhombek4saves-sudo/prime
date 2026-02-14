"""
WebhookService — register inbound webhooks that trigger agents.

Webhooks use HMAC-SHA256 signature verification (optional).
Template variables in message_template are rendered with payload fields:
  {{payload.field_name}}
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class WebhookService:
    """Manage webhook bindings and process incoming calls."""

    @staticmethod
    async def register(
        name: str,
        path: str,
        message_template: str,
        agent_id: str | None = None,
        secret: str | None = None,
    ) -> dict:
        """Create a webhook binding in DB."""
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import WebhookBinding

        if not path.startswith("/"):
            path = f"/{path}"

        binding_id = uuid.uuid4()
        with SyncSessionLocal() as db:
            binding = WebhookBinding(
                id=binding_id,
                name=name,
                path=path,
                secret=secret,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                message_template=message_template,
                active=True,
            )
            db.add(binding)
            db.commit()

        return {
            "id": str(binding_id),
            "name": name,
            "path": path,
            "agent_id": agent_id,
            "active": True,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def unregister(webhook_id: str) -> bool:
        """Delete a webhook binding."""
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import WebhookBinding

        with SyncSessionLocal() as db:
            binding = db.get(WebhookBinding, uuid.UUID(webhook_id))
            if binding:
                db.delete(binding)
                db.commit()
                return True
        return False

    @staticmethod
    def verify_signature(secret: str, payload_bytes: bytes, signature_header: str | None) -> bool:
        """Verify HMAC-SHA256 signature from X-Hub-Signature-256 header."""
        if not signature_header:
            return False
        expected = "sha256=" + hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    @staticmethod
    async def process(path: str, payload: dict, headers: dict) -> str:
        """Find the binding for path, verify signature, render template, trigger agent."""
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import WebhookBinding, Agent, Provider
        from sqlalchemy import select

        if not path.startswith("/"):
            path = f"/{path}"

        with SyncSessionLocal() as db:
            result = db.execute(
                select(WebhookBinding).where(
                    WebhookBinding.path == path,
                    WebhookBinding.active == True,  # noqa: E712
                )
            )
            binding = result.scalar_one_or_none()
            if not binding:
                return f"No active webhook found for path: {path}"

            # Signature check (if secret set)
            if binding.secret:
                import json as _json
                raw = _json.dumps(payload).encode()
                sig = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
                if not WebhookService.verify_signature(binding.secret, raw, sig):
                    return "Webhook signature verification failed"

            message = WebhookService.render_template(binding.message_template, payload)

            # Resolve agent config
            provider_type: Any = "OpenAI"
            provider_config: dict = {}
            workspace_path: str | None = None
            system: str | None = None

            if binding.agent_id:
                agent = db.get(Agent, binding.agent_id)
                if agent:
                    workspace_path = agent.workspace_path
                    system = agent.system_prompt
                    if agent.default_provider_id:
                        prov = db.get(Provider, agent.default_provider_id)
                        if prov:
                            provider_type = prov.type
                            provider_config = prov.config or {}

        # Trigger agent in background thread
        import asyncio
        from app.services.agent_runner import AgentRunner

        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            lambda: AgentRunner().run(
                message,
                provider_type=provider_type,
                provider_name="webhook",
                provider_config=provider_config,
                system=system,
                workspace_path=workspace_path,
            ),
        )
        return f"Webhook processed: triggered agent for path {path}"

    @staticmethod
    def render_template(template: str, payload: dict) -> str:
        """Replace {{payload.field}} placeholders with payload values."""
        def replacer(m: re.Match) -> str:
            field = m.group(1).strip()
            parts = field.split(".")
            value: Any = payload
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, "")
                else:
                    value = ""
                    break
            return str(value)

        return re.sub(r"\{\{(.*?)\}\}", replacer, template)

    @staticmethod
    async def list_bindings() -> list[dict]:
        """Return all webhook bindings."""
        try:
            from app.persistence.database import SyncSessionLocal
            from app.persistence.models import WebhookBinding
            from sqlalchemy import select

            with SyncSessionLocal() as db:
                result = db.execute(
                    select(WebhookBinding).order_by(WebhookBinding.created_at.desc())
                )
                return [
                    {
                        "id": str(b.id),
                        "name": b.name,
                        "path": b.path,
                        "agent_id": str(b.agent_id) if b.agent_id else None,
                        "active": b.active,
                        "created_at": b.created_at.isoformat(),
                    }
                    for b in result.scalars().all()
                ]
        except Exception as exc:
            logger.warning("list_bindings DB error: %s", exc)
            return []
