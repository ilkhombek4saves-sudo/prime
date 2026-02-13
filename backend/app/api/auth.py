from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.security import create_access_token, create_refresh_token, revoke_token, verify_password
from app.persistence.database import get_db
from app.persistence.models import User
from app.schemas.auth import (
    DeviceCompleteRequest,
    DeviceStartRequest,
    DeviceStartResponse,
    DeviceTokenRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.oauth_device_service import OAuthDeviceError, OAuthDeviceService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    refresh_token = create_refresh_token(user_id=user.id, username=user.username, role=user.role.value)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, _: dict = Depends(get_current_user)) -> None:
    """Revoke the current access token so it cannot be reused."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        revoke_token(token)


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "sub": user.get("sub"),
        "username": user.get("username"),
        "role": user.get("role"),
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = OAuthDeviceService(db)
    try:
        tokens = service.refresh(refresh_token=payload.refresh_token)
    except OAuthDeviceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return TokenResponse(**tokens)


@router.post("/device/start", response_model=DeviceStartResponse)
def device_start(payload: DeviceStartRequest, db: Session = Depends(get_db)) -> DeviceStartResponse:
    service = OAuthDeviceService(db)
    result = service.start_flow(client_name=payload.client_name, scope=payload.scope)
    return DeviceStartResponse(**result)


@router.post("/device/complete")
def device_complete(payload: DeviceCompleteRequest, db: Session = Depends(get_db)) -> dict:
    service = OAuthDeviceService(db)
    try:
        return service.complete_flow(
            user_code=payload.user_code,
            username=payload.username,
            password=payload.password,
        )
    except OAuthDeviceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc


@router.post("/device/token", response_model=TokenResponse)
def device_token(payload: DeviceTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = OAuthDeviceService(db)
    try:
        result = service.exchange_device_code(device_code=payload.device_code)
    except OAuthDeviceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return TokenResponse(**result)
