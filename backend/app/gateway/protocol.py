from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import AliasChoices

from pydantic import BaseModel, Field, ValidationError

PROTOCOL_VERSION = 3

class ProtocolError(ValueError):
    def __init__(self, code: str, message: str, req_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.req_id = req_id
        super().__init__(message)


def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class ConnectChallengeMessage(BaseModel):
    type: Literal["event"]
    event: Literal["connect.challenge"]
    payload: dict[str, Any]
    ts: int
    seq: int | None = None


class ConnectClientInfo(BaseModel):
    id: str | None = None
    name: str = "unknown"
    display_name: str | None = Field(default=None, alias="displayName")
    version: str = "0"
    platform: str | None = None
    device_family: str | None = Field(default=None, alias="deviceFamily")
    model_identifier: str | None = Field(default=None, alias="modelIdentifier")
    mode: str | None = None
    instance_id: str | None = Field(default=None, alias="instanceId")

    model_config = {"populate_by_name": True, "extra": "forbid"}


class ConnectMessage(BaseModel):
    """Legacy connect message (backward compatibility)."""
    type: Literal["connect"]
    token: str
    nonce: str
    client: ConnectClientInfo = Field(default_factory=ConnectClientInfo)


class ConnectDeviceInfo(BaseModel):
    id: str | None = None
    name: str | None = None
    nonce: str | None = None
    public_key: str | None = Field(default=None, alias="publicKey")
    signature: str | None = None
    signed_at: str | None = Field(default=None, alias="signedAt")

    model_config = {"populate_by_name": True, "extra": "forbid"}


class ConnectAuthInfo(BaseModel):
    token: str | None = None
    password: str | None = None

    model_config = {"extra": "forbid"}


class ConnectParams(BaseModel):
    token: str | None = None
    nonce: str | None = None
    client: ConnectClientInfo = Field(default_factory=ConnectClientInfo)
    role: str | None = None
    scopes: list[str] | None = None
    caps: list[str] | None = None
    commands: list[str] | None = None
    permissions: list[str] | None = None
    device: ConnectDeviceInfo | None = None
    auth: ConnectAuthInfo | None = None
    protocol: str | None = None
    min_protocol: int | None = Field(default=None, alias="minProtocol")
    max_protocol: int | None = Field(default=None, alias="maxProtocol")
    locale: str | None = None
    user_agent: str | None = Field(default=None, alias="userAgent")

    model_config = {"populate_by_name": True, "extra": "forbid"}


class RequestMessage(BaseModel):
    type: Literal["req"]
    id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None

    model_config = {"extra": "forbid"}


class ResponseMessage(BaseModel):
    type: Literal["res"]
    id: str
    ok: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class ErrorMessage(BaseModel):
    type: Literal["error"]
    id: str | None = None
    code: str
    message: str

    model_config = {"extra": "forbid"}


class EventMessage(BaseModel):
    type: Literal["event"]
    event: str
    payload: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payload", "data"),
    )
    ts: int
    seq: int | None = None
    state_version: int | None = Field(default=None, alias="stateVersion")

    model_config = {"populate_by_name": True, "extra": "forbid"}

class ConnectRequest(BaseModel):
    token: str | None = None
    nonce: str | None = None
    client: ConnectClientInfo = Field(default_factory=ConnectClientInfo)
    role: str | None = None
    scopes: list[str] | None = None
    caps: list[str] | None = None
    commands: list[str] | None = None
    permissions: list[str] | None = None
    device: ConnectDeviceInfo | None = None
    auth: ConnectAuthInfo | None = None
    protocol: str | None = None
    min_protocol: int | None = None
    max_protocol: int | None = None
    locale: str | None = None
    user_agent: str | None = None


def make_challenge(nonce: str) -> ConnectChallengeMessage:
    return ConnectChallengeMessage(
        type="event",
        event="connect.challenge",
        payload={
            "nonce": nonce,
            "serverTime": utc_now_ms(),
            "protocol": PROTOCOL_VERSION,
        },
        ts=utc_now_ms(),
    )


def parse_connect(payload: dict[str, Any]) -> ConnectMessage:
    try:
        return ConnectMessage.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError(code="invalid_connect", message=str(exc)) from exc


def parse_connect_request(payload: dict[str, Any]) -> ConnectRequest:
    if payload.get("type") != "req" or payload.get("method") != "connect":
        raise ProtocolError(code="invalid_connect", message="connect request required")
    try:
        params = ConnectParams.model_validate(payload.get("params") or {})
    except ValidationError as exc:
        raise ProtocolError(code="invalid_connect", message=str(exc)) from exc

    token = params.token or (params.auth.token if params.auth else None)
    password = params.auth.password if params.auth else None
    if not token and not password:
        raise ProtocolError(code="invalid_connect", message="token or password is required")

    return ConnectRequest(
        token=token,
        nonce=params.nonce,
        client=params.client,
        role=params.role,
        scopes=params.scopes,
        caps=params.caps,
        commands=params.commands,
        permissions=params.permissions,
        device=params.device,
        auth=params.auth,
        protocol=params.protocol,
        min_protocol=params.min_protocol,
        max_protocol=params.max_protocol,
        locale=params.locale,
        user_agent=params.user_agent,
    )


def parse_request(payload: dict[str, Any]) -> RequestMessage:
    try:
        return RequestMessage.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError(code="invalid_request", message=str(exc)) from exc


def make_response(req_id: str, payload: dict[str, Any]) -> ResponseMessage:
    return ResponseMessage(type="res", id=req_id, ok=True, payload=payload)


def make_error(code: str, message: str, req_id: str | None = None) -> ErrorMessage:
    return ErrorMessage(type="error", id=req_id, code=code, message=message)


def make_event(event: str, payload: dict[str, Any] | None = None, seq: int | None = None) -> EventMessage:
    return EventMessage(type="event", event=event, payload=payload or {}, ts=utc_now_ms(), seq=seq)
