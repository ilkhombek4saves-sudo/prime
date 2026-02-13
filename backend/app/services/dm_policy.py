from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.persistence.models import DMPolicy, PairedDevice


@dataclass
class DMPolicyDecision:
    allowed: bool
    reason: str


class DMPolicyService:
    def __init__(self, db: Session):
        self.db = db

    def is_paired(
        self,
        *,
        channel: str,
        device_id: str | None,
        account_id: str | None,
        peer: str | None,
    ) -> bool:
        if not device_id and not (account_id or peer):
            return False

        query = self.db.query(PairedDevice).filter(
            PairedDevice.channel == channel,
            PairedDevice.active.is_(True),
        )

        if device_id:
            query = query.filter(PairedDevice.device_id == device_id)
        else:
            if account_id is not None:
                query = query.filter(PairedDevice.account_id == account_id)
            if peer is not None:
                query = query.filter(PairedDevice.peer == peer)

        return query.first() is not None

    @staticmethod
    def evaluate(
        *,
        policy: DMPolicy,
        sender_user_id: int | None,
        allowed_user_ids: list[int] | None,
        paired: bool,
        is_group: bool,
        bot_mentioned: bool,
        group_requires_mention: bool,
    ) -> DMPolicyDecision:
        allowlist = set(allowed_user_ids or [])

        if is_group and group_requires_mention and not bot_mentioned:
            return DMPolicyDecision(allowed=False, reason="bot_mention_required")

        if policy == DMPolicy.disabled:
            return DMPolicyDecision(allowed=False, reason="dm_disabled")

        if policy == DMPolicy.open:
            return DMPolicyDecision(allowed=True, reason="open_policy")

        if policy == DMPolicy.allowlist:
            if sender_user_id in allowlist:
                return DMPolicyDecision(allowed=True, reason="allowlist")
            return DMPolicyDecision(allowed=False, reason="sender_not_in_allowlist")

        # pairing policy
        if paired:
            return DMPolicyDecision(allowed=True, reason="paired_device")
        if sender_user_id in allowlist:
            return DMPolicyDecision(allowed=True, reason="allowlisted_sender")
        return DMPolicyDecision(allowed=False, reason="pairing_required")
