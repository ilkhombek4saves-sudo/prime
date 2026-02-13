from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.binding_resolver import BindingResolver


BASE = datetime.now(timezone.utc)


def _binding(account_id, peer, priority, offset_seconds):
    return SimpleNamespace(
        account_id=account_id,
        peer=peer,
        priority=priority,
        created_at=BASE + timedelta(seconds=offset_seconds),
    )


def test_binding_resolver_prefers_most_specific_match():
    candidates = [
        _binding(account_id=None, peer=None, priority=999, offset_seconds=1),
        _binding(account_id="acc-1", peer=None, priority=10, offset_seconds=2),
        _binding(account_id="acc-1", peer="peer-1", priority=1, offset_seconds=3),
    ]

    best = BindingResolver.select_best(candidates, account_id="acc-1", peer="peer-1")
    assert best.account_id == "acc-1"
    assert best.peer == "peer-1"


def test_binding_resolver_ignores_incompatible_candidates():
    candidates = [
        _binding(account_id="acc-2", peer=None, priority=500, offset_seconds=1),
        _binding(account_id=None, peer=None, priority=100, offset_seconds=2),
    ]

    best = BindingResolver.select_best(candidates, account_id="acc-1", peer=None)
    assert best.account_id is None
    assert best.peer is None


def test_binding_resolver_priority_breaks_tie():
    candidates = [
        _binding(account_id="acc-1", peer=None, priority=10, offset_seconds=1),
        _binding(account_id="acc-1", peer=None, priority=99, offset_seconds=2),
    ]

    best = BindingResolver.select_best(candidates, account_id="acc-1", peer="peer-x")
    assert best.priority == 99
