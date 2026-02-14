"""
Tailscale API — manage Tailscale network via CLI wrapper.

GET    /api/tailscale/status
POST   /api/tailscale/connect   body: {auth_key}
POST   /api/tailscale/serve     body: {port}
POST   /api/tailscale/funnel    body: {port}
DELETE /api/tailscale/funnel
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.persistence.models import User

router = APIRouter(prefix="/tailscale", tags=["tailscale"])


class ConnectRequest(BaseModel):
    auth_key: str


class ServeRequest(BaseModel):
    port: int = 8000


@router.get("/status")
async def tailscale_status(current_user: User = Depends(get_current_user)):
    from app.services.tailscale_service import TailscaleService

    if not TailscaleService.is_installed():
        return {"installed": False, "connected": False}

    status = TailscaleService.status()
    return {
        "installed": True,
        "connected": status.connected,
        "hostname": status.hostname,
        "tailnet_ip": status.tailnet_ip,
        "funnel_url": status.funnel_url,
        "peers": status.peers or [],
    }


@router.post("/connect")
async def tailscale_connect(
    body: ConnectRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.tailscale_service import TailscaleService

    if not TailscaleService.is_installed():
        raise HTTPException(status_code=503, detail="Tailscale CLI not installed")

    success, message = TailscaleService.connect(body.auth_key)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"status": "connected", "message": message}


@router.post("/serve")
async def tailscale_serve(
    body: ServeRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.tailscale_service import TailscaleService

    if not TailscaleService.is_installed():
        raise HTTPException(status_code=503, detail="Tailscale CLI not installed")

    success, message = TailscaleService.serve(body.port)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"status": "serving", "port": body.port, "message": message}


@router.post("/funnel")
async def tailscale_funnel(
    body: ServeRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.tailscale_service import TailscaleService

    if not TailscaleService.is_installed():
        raise HTTPException(status_code=503, detail="Tailscale CLI not installed")

    success, message = TailscaleService.funnel(body.port)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    url = TailscaleService.get_funnel_url()
    return {"status": "funneling", "port": body.port, "url": url, "message": message}


@router.delete("/funnel")
async def tailscale_stop_funnel(current_user: User = Depends(get_current_user)):
    from app.services.tailscale_service import TailscaleService

    if not TailscaleService.is_installed():
        raise HTTPException(status_code=503, detail="Tailscale CLI not installed")

    success, message = TailscaleService.stop_funnel()
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"status": "stopped", "message": message}
