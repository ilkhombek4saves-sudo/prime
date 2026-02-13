#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.human_engine import HumanInteractionEngine  # noqa: E402


DEFAULT_BASE_URL = os.getenv("PRIME_API_URL", "http://localhost:8000").rstrip("/")
AUTH_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "prime"
AUTH_FILE = AUTH_DIR / "auth.json"


def _http_json(method: str, url: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data_raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(data_raw) if data_raw.strip() else {}
            return resp.status, data
    except urllib.error.HTTPError as exc:
        payload_raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(payload_raw) if payload_raw.strip() else {}
        except json.JSONDecodeError:
            parsed = {"detail": payload_raw}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"detail": f"Connection error: {exc}"}


def _auth_load() -> dict[str, Any] | None:
    if not AUTH_FILE.exists():
        return None
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _auth_save(data: dict[str, Any]) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _auth_clear() -> None:
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()


def _jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(decoded.decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _build_human_engine(enabled: bool, seed: int | None = None) -> HumanInteractionEngine:
    return HumanInteractionEngine.from_config(
        {
            "enabled": enabled,
            "think_delay_min_ms": 120,
            "think_delay_max_ms": 520,
            "oauth_poll_jitter_ratio": 0.2,
            "max_total_delay_ms": 1600,
        },
        seed=seed,
    )


def cmd_login_password(args: argparse.Namespace) -> int:
    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    status, payload = _http_json(
        "POST",
        f"{args.base_url}/api/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        print(f"Login failed ({status}): {payload.get('detail')}")
        return 1
    _auth_save(
        {
            "base_url": args.base_url,
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "token_type": payload.get("token_type", "bearer"),
            "obtained_at": int(time.time()),
            "flow": "password",
        }
    )
    print("Login successful")
    return 0


def cmd_login_device(args: argparse.Namespace) -> int:
    engine = _build_human_engine(enabled=not args.no_human, seed=args.seed)
    engine.sleep_think(complexity=2)

    status, start_payload = _http_json(
        "POST",
        f"{args.base_url}/api/auth/device/start",
        {"client_name": "prime-cli", "scope": args.scope},
    )
    if status != 200:
        print(f"Device flow start failed ({status}): {start_payload.get('detail')}")
        return 1

    user_code = start_payload["user_code"]
    print(f"Open: {start_payload['verification_uri']}")
    print(f"Code: {user_code}")

    username = args.username or input("Approve as username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    engine.sleep_think(complexity=3)

    complete_status, complete_payload = _http_json(
        "POST",
        f"{args.base_url}/api/auth/device/complete",
        {"user_code": user_code, "username": username, "password": password},
    )
    if complete_status != 200:
        detail = complete_payload.get("detail", complete_payload)
        print(f"Approval failed ({complete_status}): {detail}")
        return 1

    expires_in = int(start_payload.get("expires_in", 900))
    interval = float(start_payload.get("interval", 3))
    deadline = time.time() + expires_in
    device_code = start_payload["device_code"]

    while time.time() < deadline:
        poll_status, poll_payload = _http_json(
            "POST",
            f"{args.base_url}/api/auth/device/token",
            {"device_code": device_code},
        )
        if poll_status == 200:
            _auth_save(
                {
                    "base_url": args.base_url,
                    "access_token": poll_payload.get("access_token"),
                    "refresh_token": poll_payload.get("refresh_token"),
                    "token_type": poll_payload.get("token_type", "bearer"),
                    "obtained_at": int(time.time()),
                    "flow": "device",
                }
            )
            print("Device login successful")
            return 0

        detail = poll_payload.get("detail", {})
        error_code = detail.get("error") if isinstance(detail, dict) else None
        if poll_status == 428 or error_code == "authorization_pending":
            wait_s = engine.jittered_poll_interval(interval)
            time.sleep(wait_s)
            continue
        print(f"Token polling failed ({poll_status}): {detail}")
        return 1

    print("Device login timed out")
    return 1


def cmd_refresh(args: argparse.Namespace) -> int:
    auth = _auth_load()
    if not auth:
        print("Not logged in")
        return 1
    refresh_token = auth.get("refresh_token")
    if not refresh_token:
        print("No refresh token found")
        return 1
    status, payload = _http_json(
        "POST",
        f"{auth.get('base_url', DEFAULT_BASE_URL)}/api/auth/refresh",
        {"refresh_token": refresh_token},
    )
    if status != 200:
        print(f"Refresh failed ({status}): {payload.get('detail')}")
        return 1
    auth["access_token"] = payload.get("access_token")
    auth["refresh_token"] = payload.get("refresh_token")
    auth["token_type"] = payload.get("token_type", "bearer")
    auth["obtained_at"] = int(time.time())
    _auth_save(auth)
    print("Token refreshed")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    auth = _auth_load()
    if not auth:
        print("Auth status: logged_out")
        return 0
    payload = _jwt_payload(auth.get("access_token", ""))
    exp = payload.get("exp")
    remaining = None
    if exp:
        remaining = int(exp - time.time())
    username = payload.get("username", "unknown")
    role = payload.get("role", "unknown")
    print("Auth status: logged_in")
    print(f"User: {username} ({role})")
    if remaining is not None:
        print(f"Access token TTL: {max(0, remaining)}s")
    print(f"Flow: {auth.get('flow', 'unknown')}")
    print(f"Base URL: {auth.get('base_url', DEFAULT_BASE_URL)}")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    auth = _auth_load()
    if not auth or not auth.get("access_token"):
        print("Not logged in")
        return 1
    status, payload = _http_json(
        "GET",
        f"{auth.get('base_url', DEFAULT_BASE_URL)}/api/auth/me",
        token=auth["access_token"],
    )
    if status != 200:
        print(f"whoami failed ({status}): {payload.get('detail')}")
        return 1
    print(f"{payload.get('username')} ({payload.get('role')})")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    _auth_clear()
    print("Logged out")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prime auth helper")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_login = sub.add_parser("login", help="OAuth-like device login flow")
    p_login.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_login.add_argument("--scope", default="agent:run")
    p_login.add_argument("--username")
    p_login.add_argument("--password")
    p_login.add_argument("--no-human", action="store_true")
    p_login.add_argument("--seed", type=int, default=None)
    p_login.set_defaults(func=cmd_login_device)

    p_legacy = sub.add_parser("login-password", help="Legacy username/password login")
    p_legacy.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_legacy.add_argument("--username")
    p_legacy.add_argument("--password")
    p_legacy.set_defaults(func=cmd_login_password)

    p_refresh = sub.add_parser("refresh", help="Refresh tokens")
    p_refresh.set_defaults(func=cmd_refresh)

    p_status = sub.add_parser("status", help="Show login status")
    p_status.set_defaults(func=cmd_status)

    p_whoami = sub.add_parser("whoami", help="Query authenticated user")
    p_whoami.set_defaults(func=cmd_whoami)

    p_logout = sub.add_parser("logout", help="Logout and clear tokens")
    p_logout.set_defaults(func=cmd_logout)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
