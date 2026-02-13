from app.persistence.models import DMPolicy
from app.services.dm_policy import DMPolicyService


def test_open_policy_allows_direct_message():
    decision = DMPolicyService.evaluate(
        policy=DMPolicy.open,
        sender_user_id=1,
        allowed_user_ids=[],
        paired=False,
        is_group=False,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    assert decision.allowed is True


def test_disabled_policy_denies():
    decision = DMPolicyService.evaluate(
        policy=DMPolicy.disabled,
        sender_user_id=1,
        allowed_user_ids=[1],
        paired=True,
        is_group=False,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    assert decision.allowed is False
    assert decision.reason == "dm_disabled"


def test_allowlist_policy_requires_sender_in_allowlist():
    denied = DMPolicyService.evaluate(
        policy=DMPolicy.allowlist,
        sender_user_id=2,
        allowed_user_ids=[1],
        paired=False,
        is_group=False,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    allowed = DMPolicyService.evaluate(
        policy=DMPolicy.allowlist,
        sender_user_id=1,
        allowed_user_ids=[1],
        paired=False,
        is_group=False,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    assert denied.allowed is False
    assert allowed.allowed is True


def test_pairing_policy_allows_paired_device():
    decision = DMPolicyService.evaluate(
        policy=DMPolicy.pairing,
        sender_user_id=5,
        allowed_user_ids=[],
        paired=True,
        is_group=False,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    assert decision.allowed is True
    assert decision.reason == "paired_device"


def test_group_requires_mention_gate():
    decision = DMPolicyService.evaluate(
        policy=DMPolicy.open,
        sender_user_id=1,
        allowed_user_ids=[],
        paired=False,
        is_group=True,
        bot_mentioned=False,
        group_requires_mention=True,
    )
    assert decision.allowed is False
    assert decision.reason == "bot_mention_required"
