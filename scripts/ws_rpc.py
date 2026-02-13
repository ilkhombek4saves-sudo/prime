#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketError(RuntimeError):
    pass


def normalize_ws_url(raw: str, *, default_path: str = "/api/ws/events") -> str:
    """
    Accept ws(s)://, http(s)://, or host:port and normalize to a concrete WS URL.

    OpenClaw-style examples commonly omit the path. Our gateway WS endpoint lives at /api/ws/events,
    so we append it when the URL has no path (or "/").
    """
    value = (raw or "").strip()
    if not value:
        raise ValueError("url is required")

    if "://" not in value:
        value = "ws://" + value

    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        scheme = "wss" if scheme == "https" else "ws"

    if scheme not in {"ws", "wss"}:
        raise ValueError(f"unsupported url scheme: {parsed.scheme}")

    path = parsed.path or ""
    if path in {"", "/"}:
        path = default_path

    normalized = parsed._replace(scheme=scheme, path=path)
    return urlunparse(normalized)


def _sha1_base64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha1(data).digest()).decode("ascii")


def _rand_key() -> str:
    return base64.b64encode(os.urandom(16)).decode("ascii")


def _mask(payload: bytes, mask_key: bytes) -> bytes:
    out = bytearray(len(payload))
    for i, b in enumerate(payload):
        out[i] = b ^ mask_key[i % 4]
    return bytes(out)


def _encode_client_frame(opcode: int, payload: bytes) -> bytes:
    # Client-to-server frames MUST be masked.
    fin_opcode = 0x80 | (opcode & 0x0F)
    length = len(payload)
    mask_bit = 0x80
    header = bytearray()
    header.append(fin_opcode)
    if length <= 125:
        header.append(mask_bit | length)
    elif length <= 0xFFFF:
        header.append(mask_bit | 126)
        header += struct.pack("!H", length)
    else:
        header.append(mask_bit | 127)
        header += struct.pack("!Q", length)

    mask_key = os.urandom(4)
    header += mask_key
    return bytes(header) + _mask(payload, mask_key)


@dataclass
class _SocketReader:
    sock: socket.socket
    buf: bytearray

    def recv_exact(self, n: int) -> bytes:
        if n <= 0:
            return b""
        while len(self.buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self.buf)))
            if not chunk:
                raise WebSocketError("connection closed")
            self.buf += chunk
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def recv_until(self, needle: bytes, limit: int = 65536) -> tuple[bytes, bytes]:
        while needle not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketError("connection closed during handshake")
            self.buf += chunk
            if len(self.buf) > limit:
                raise WebSocketError("handshake response too large")
        idx = self.buf.index(needle)
        head = bytes(self.buf[:idx])
        rest = bytes(self.buf[idx + len(needle):])
        self.buf = bytearray(rest)
        return head, rest


class WebSocket:
    def __init__(self, sock: socket.socket, *, reader: _SocketReader) -> None:
        self.sock = sock
        self._r = reader

    @classmethod
    def connect(cls, url: str, *, timeout_s: float = 10.0, user_agent: str = "prime-cli") -> "WebSocket":
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in {"ws", "wss"}:
            raise WebSocketError(f"unsupported scheme: {scheme}")

        host = parsed.hostname
        if not host:
            raise WebSocketError("missing host")
        port = parsed.port or (443 if scheme == "wss" else 80)

        path = parsed.path or "/"
        if parsed.query:
            path = path + "?" + parsed.query

        sock = socket.create_connection((host, port), timeout=timeout_s)
        if scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)

        sock.settimeout(timeout_s)
        reader = _SocketReader(sock=sock, buf=bytearray())

        key = _rand_key()
        req_lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            f"User-Agent: {user_agent}",
        ]
        req = ("\r\n".join(req_lines) + "\r\n\r\n").encode("utf-8")
        sock.sendall(req)

        raw_head, _ = reader.recv_until(b"\r\n\r\n")
        head = raw_head.decode("iso-8859-1", errors="replace")
        lines = head.split("\r\n")
        status = lines[0].strip()
        if not status.startswith("HTTP/1.1 101"):
            raise WebSocketError(f"handshake failed: {status}")

        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

        accept = headers.get("sec-websocket-accept", "")
        expected = _sha1_base64((key + _WS_GUID).encode("utf-8"))
        if accept.lower() != expected.lower():
            raise WebSocketError("handshake failed: invalid Sec-WebSocket-Accept")

        return cls(sock, reader=reader)

    def close(self) -> None:
        try:
            self.sock.sendall(_encode_client_frame(0x8, b""))
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def send_text(self, text: str) -> None:
        self.sock.sendall(_encode_client_frame(0x1, text.encode("utf-8")))

    def send_json(self, payload: dict[str, Any]) -> None:
        self.send_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))

    def _recv_frame(self) -> tuple[int, bytes]:
        b1, b2 = self._r.recv_exact(2)
        fin = (b1 & 0x80) != 0
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        if length == 126:
            (length,) = struct.unpack("!H", self._r.recv_exact(2))
        elif length == 127:
            (length,) = struct.unpack("!Q", self._r.recv_exact(8))

        mask_key = b""
        if masked:
            mask_key = self._r.recv_exact(4)

        payload = self._r.recv_exact(int(length))
        if masked:
            payload = _mask(payload, mask_key)

        if not fin and opcode in {0x1, 0x2}:
            # Fragmentation isn't expected for our small JSON messages. Keep behavior explicit.
            raise WebSocketError("fragmented frames are not supported")

        return opcode, payload

    def recv_json(self) -> dict[str, Any]:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise WebSocketError("server closed connection")
            if opcode == 0x9:
                # Ping -> Pong.
                self.sock.sendall(_encode_client_frame(0xA, payload))
                continue
            if opcode == 0xA:
                continue
            if opcode != 0x1:
                continue

            try:
                text = payload.decode("utf-8", errors="replace")
                parsed = json.loads(text) if text.strip() else {}
            except Exception as exc:
                raise WebSocketError(f"invalid JSON frame: {exc}") from exc

            if not isinstance(parsed, dict):
                raise WebSocketError("expected JSON object frame")
            return parsed


@dataclass
class ConnectResult:
    req_id: str
    payload: dict[str, Any]


class WSRPCClient:
    def __init__(
        self,
        *,
        url: str,
        token: str | None = None,
        password: str | None = None,
        timeout_ms: int = 10_000,
        client_name: str = "prime-cli",
        client_version: str = "0",
        platform: str | None = None,
    ) -> None:
        if not token and not password:
            raise ValueError("token or password is required")
        self.url = url
        self.token = token
        self.password = password
        self.timeout_ms = max(250, int(timeout_ms))
        self.client_name = client_name
        self.client_version = client_version
        self.platform = platform
        self._ws: WebSocket | None = None

    def _deadline(self) -> float:
        return time.monotonic() + (self.timeout_ms / 1000.0)

    def _recv_with_deadline(self, *, deadline: float) -> dict[str, Any]:
        if self._ws is None:
            raise WebSocketError("not connected")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("websocket operation timed out")
            self._ws.sock.settimeout(max(0.25, remaining))
            try:
                return self._ws.recv_json()
            except socket.timeout as exc:
                # Loop until global deadline.
                continue
            except TimeoutError:
                raise
            except Exception as exc:
                raise

    def connect(self) -> ConnectResult:
        deadline = self._deadline()
        ws = WebSocket.connect(self.url, timeout_s=self.timeout_ms / 1000.0)
        self._ws = ws

        challenge = self._recv_with_deadline(deadline=deadline)
        if not (challenge.get("type") == "event" and challenge.get("event") == "connect.challenge"):
            raise WebSocketError("expected connect.challenge")

        nonce = ((challenge.get("payload") or {}) if isinstance(challenge.get("payload"), dict) else {}).get("nonce")
        if not nonce:
            raise WebSocketError("connect.challenge missing nonce")

        req_id = uuid.uuid4().hex
        params: dict[str, Any] = {
            "nonce": nonce,
            "client": {
                "name": self.client_name,
                "version": self.client_version,
                "platform": self.platform,
            },
            "minProtocol": 3,
            "maxProtocol": 3,
        }
        if self.token:
            params["token"] = self.token
        else:
            params["auth"] = {"password": self.password}

        ws.send_json({"type": "req", "id": req_id, "method": "connect", "params": params})

        while True:
            msg = self._recv_with_deadline(deadline=deadline)
            if msg.get("type") == "res" and msg.get("id") == req_id:
                payload = msg.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {"payload": payload}
                return ConnectResult(req_id=req_id, payload=payload)
            if msg.get("type") == "error" and msg.get("id") == req_id:
                raise WebSocketError(f"connect failed: {msg.get('code')}: {msg.get('message')}")
            # ignore events/other traffic

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        expect_final: bool = False,
    ) -> dict[str, Any]:
        if self._ws is None:
            raise WebSocketError("not connected")
        deadline = self._deadline()
        req_id = uuid.uuid4().hex
        payload: dict[str, Any] = {"type": "req", "id": req_id, "method": method, "params": params or {}}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        self._ws.send_json(payload)

        # expect_final is OpenClaw-compatible plumbing; our current server responds immediately.
        _ = expect_final

        while True:
            msg = self._recv_with_deadline(deadline=deadline)
            if msg.get("type") == "res" and msg.get("id") == req_id:
                data = msg.get("payload") or {}
                if not isinstance(data, dict):
                    data = {"payload": data}
                return data
            if msg.get("type") == "error" and msg.get("id") == req_id:
                code = msg.get("code") or "error"
                message = msg.get("message") or "request failed"
                raise WebSocketError(f"{code}: {message}")
            # ignore events/other traffic

    def shutdown(self) -> None:
        if self._ws is None:
            return
        self._ws.close()
        self._ws = None

