from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class HumanizationProfile:
    enabled: bool = False
    think_delay_min_ms: int = 120
    think_delay_max_ms: int = 640
    typing_cps_min: float = 18.0
    typing_cps_max: float = 34.0
    chunk_chars_min: int = 8
    chunk_chars_max: int = 28
    punctuation_pause_ms: int = 90
    oauth_poll_jitter_ratio: float = 0.2
    max_total_delay_ms: int = 2200


class HumanInteractionEngine:
    """Utility for human-like pacing in CLI/OAuth interactions."""

    def __init__(self, profile: HumanizationProfile | None = None, seed: int | None = None) -> None:
        self.profile = profile or HumanizationProfile()
        self._rng = random.Random(seed)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None, seed: int | None = None) -> "HumanInteractionEngine":
        cfg = config or {}
        profile = HumanizationProfile(
            enabled=bool(cfg.get("enabled", False)),
            think_delay_min_ms=cls._as_int(cfg.get("think_delay_min_ms"), 120),
            think_delay_max_ms=cls._as_int(cfg.get("think_delay_max_ms"), 640),
            typing_cps_min=cls._as_float(cfg.get("typing_cps_min"), 18.0),
            typing_cps_max=cls._as_float(cfg.get("typing_cps_max"), 34.0),
            chunk_chars_min=cls._as_int(cfg.get("chunk_chars_min"), 8),
            chunk_chars_max=cls._as_int(cfg.get("chunk_chars_max"), 28),
            punctuation_pause_ms=cls._as_int(cfg.get("punctuation_pause_ms"), 90),
            oauth_poll_jitter_ratio=cls._as_float(cfg.get("oauth_poll_jitter_ratio"), 0.2),
            max_total_delay_ms=max(0, cls._as_int(cfg.get("max_total_delay_ms"), 2200)),
        )
        if profile.typing_cps_min <= 0:
            profile.typing_cps_min = 18.0
        if profile.typing_cps_max < profile.typing_cps_min:
            profile.typing_cps_max = profile.typing_cps_min
        if profile.chunk_chars_min <= 0:
            profile.chunk_chars_min = 8
        if profile.chunk_chars_max < profile.chunk_chars_min:
            profile.chunk_chars_max = profile.chunk_chars_min
        if profile.think_delay_max_ms < profile.think_delay_min_ms:
            profile.think_delay_max_ms = profile.think_delay_min_ms
        if profile.oauth_poll_jitter_ratio < 0:
            profile.oauth_poll_jitter_ratio = 0.0
        return cls(profile=profile, seed=seed)

    def sleep_think(self, complexity: int = 0) -> int:
        if not self.profile.enabled:
            return 0
        extra = max(0, complexity) * 25
        base = self._rng.randint(
            self.profile.think_delay_min_ms,
            self.profile.think_delay_max_ms,
        ) + extra
        delay_ms = min(base, self.profile.max_total_delay_ms)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        return delay_ms

    def split_for_typing(self, text: str) -> list[str]:
        if not text:
            return []
        chunks: list[str] = []
        i = 0
        while i < len(text):
            step = self._rng.randint(self.profile.chunk_chars_min, self.profile.chunk_chars_max)
            chunks.append(text[i:i + step])
            i += step
        return chunks

    def chunk_delay_ms(self, chunk: str) -> int:
        if not chunk:
            return 0
        cps = self._rng.uniform(self.profile.typing_cps_min, self.profile.typing_cps_max)
        ms = int(max(1, len(chunk)) / max(cps, 1) * 1000)
        if chunk[-1:] in ".!?;:":
            ms += self.profile.punctuation_pause_ms
        return ms

    def pace_text(self, text: str) -> tuple[list[str], int]:
        chunks = self.split_for_typing(text)
        if not self.profile.enabled:
            return chunks, 0

        spent = 0
        for chunk in chunks:
            delay_ms = self.chunk_delay_ms(chunk)
            if spent + delay_ms > self.profile.max_total_delay_ms:
                break
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
                spent += delay_ms
        return chunks, spent

    def jittered_poll_interval(self, base_seconds: float) -> float:
        base = max(0.25, float(base_seconds))
        ratio = self.profile.oauth_poll_jitter_ratio if self.profile.enabled else 0.0
        delta = base * ratio
        low = max(0.25, base - delta)
        high = max(low, base + delta)
        return self._rng.uniform(low, high)

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
