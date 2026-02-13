from __future__ import annotations

from app.services.human_engine import HumanInteractionEngine


def test_human_engine_split_chunks_deterministic():
    engine = HumanInteractionEngine.from_config(
        {
            "enabled": True,
            "chunk_chars_min": 4,
            "chunk_chars_max": 4,
        },
        seed=7,
    )
    chunks = engine.split_for_typing("hello-human-engine")
    assert chunks == ["hell", "o-hu", "man-", "engi", "ne"]


def test_human_engine_jitter_disabled_returns_base():
    engine = HumanInteractionEngine.from_config({"enabled": False}, seed=1)
    assert engine.jittered_poll_interval(3.0) == 3.0


def test_human_engine_jitter_within_bounds():
    engine = HumanInteractionEngine.from_config(
        {"enabled": True, "oauth_poll_jitter_ratio": 0.25},
        seed=1,
    )
    value = engine.jittered_poll_interval(4.0)
    assert 3.0 <= value <= 5.0
