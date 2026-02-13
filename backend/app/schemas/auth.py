from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceStartRequest(BaseModel):
    client_name: str = "prime-cli"
    scope: str = "agent:run"


class DeviceStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceCompleteRequest(BaseModel):
    user_code: str
    username: str
    password: str


class DeviceTokenRequest(BaseModel):
    device_code: str
