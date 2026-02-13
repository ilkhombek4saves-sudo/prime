"""
In-memory token blacklist for logout / revocation.

Uses a set of (jti, exp) tuples. Expired tokens are cleaned up periodically
so memory doesn't grow unbounded.

Limitation: resets on restart — acceptable for a single-node deployment.
For multi-node, swap the set for a Redis SETEX.
"""
from __future__ import annotations

import threading
from time import time


class TokenBlacklist:
    def __init__(self) -> None:
        self._revoked: dict[str, float] = {}  # jti → exp (unix timestamp)
        self._lock = threading.Lock()

    def revoke(self, jti: str, exp: float) -> None:
        """Mark a token as revoked until its natural expiry."""
        with self._lock:
            self._revoked[jti] = exp
            self._cleanup()

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            return jti in self._revoked

    def _cleanup(self) -> None:
        now = time()
        expired = [k for k, exp in self._revoked.items() if exp < now]
        for k in expired:
            del self._revoked[k]


_blacklist = TokenBlacklist()


def get_blacklist() -> TokenBlacklist:
    return _blacklist
