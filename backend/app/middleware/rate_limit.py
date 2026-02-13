from collections import defaultdict, deque
from time import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Auth endpoints get a much tighter per-IP window to prevent brute-force.
_AUTH_PATHS = {"/api/auth/login", "/api/auth/refresh", "/api/auth/device/token"}
_AUTH_LIMIT = 10      # max attempts per minute per IP on auth endpoints
_GLOBAL_LIMIT = 120   # general limit for all other endpoints


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client fixed-window rate limiter.

    - Auth endpoints: 10 req/min per IP  (brute-force protection)
    - Everything else: 120 req/min per IP (general protection)
    """

    def __init__(self, app, requests_per_minute: int = _GLOBAL_LIMIT):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._global_windows: dict[str, deque] = defaultdict(deque)
        self._auth_windows: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        now = time()

        # Strict auth limit
        if path in _AUTH_PATHS:
            bucket = self._auth_windows[client_ip]
            self._evict(bucket, now)
            if len(bucket) >= _AUTH_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many auth attempts — wait 60 seconds"},
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)

        # Global limit
        bucket = self._global_windows[client_ip]
        self._evict(bucket, now)
        if len(bucket) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"},
            )
        bucket.append(now)

        return await call_next(request)

    @staticmethod
    def _evict(bucket: deque, now: float) -> None:
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
