from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str, req_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.req_id = req_id
        super().__init__(message)


class ConnectChallengeMessage(BaseModel):
    type: Literal["connect.challenge"]
    protocol: str = "ws.v1"
    nonce: str
    server_time: str


class ConnectClientInfo(BaseModel):
    name: str = "unknown"
    version: str = "0"


class ConnectMessage(BaseModel):
    type: Literal["connect"]
    token: str
    nonce: str
    client: ConnectClientInfo = Field(default_factory=ConnectClientInfo)


class RequestMessage(BaseModel):
    type: Literal["req"]
    id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ResponseMessage(BaseModel):
    type: Literal["res"]
    id: str
    ok: bool = True
    result: dict[str, Any] = Field(default_factory=dict)


class ErrorMessage(BaseModel):
    type: Literal["error"]
    id: str | None = None
    code: str
    message: str


class EventMessage(BaseModel):
    type: Literal["event"]
    event: str
    data: dict[str, Any] = Field(default_factory=dict)
    ts: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_challenge(nonce: str) -> ConnectChallengeMessage:
    return ConnectChallengeMessage(type="connect.challenge", nonce=nonce, server_time=utc_now_iso())


def parse_connect(payload: dict[str, Any]) -> ConnectMessage:
    try:
        return ConnectMessage.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError(code="invalid_connect", message=str(exc)) from exc


def parse_request(payload: dict[str, Any]) -> RequestMessage:
    try:
        return RequestMessage.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError(code="invalid_request", message=str(exc)) from exc


def make_response(req_id: str, result: dict[str, Any]) -> ResponseMessage:
    return ResponseMessage(type="res", id=req_id, ok=True, result=result)


def make_error(code: str, message: str, req_id: str | None = None) -> ErrorMessage:
    return ErrorMessage(type="error", id=req_id, code=code, message=message)


def make_event(event: str, data: dict[str, Any] | None = None) -> EventMessage:
    return EventMessage(type="event", event=event, data=data or {}, ts=utc_now_iso())
