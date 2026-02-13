from __future__ import annotations

import ipaddress
from typing import Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config.settings import get_settings


def _parse_cidrs(raw: str | None) -> list[ipaddress._BaseNetwork]:
    if not raw:
        return []
    cidrs = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            cidrs.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            continue
    return cidrs


def _is_trusted(ip: str, networks: Iterable[ipaddress._BaseNetwork]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


class TrustedProxyMiddleware(BaseHTTPMiddleware):
    """Reject forwarded headers unless request comes from trusted proxy CIDRs."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.allow_forwarded_headers:
            return await call_next(request)

        client = request.client
        client_ip = client.host if client else ""
        trusted = _parse_cidrs(settings.trusted_proxy_cidrs)

        has_forwarded = any(
            header in request.headers for header in (
                "x-forwarded-for",
                "x-forwarded-proto",
                "x-forwarded-host",
                "forwarded",
            )
        )
        if has_forwarded and not _is_trusted(client_ip, trusted):
            return JSONResponse(
                status_code=400,
                content={"detail": "Untrusted proxy headers"},
            )

        return await call_next(request)
