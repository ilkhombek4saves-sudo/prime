#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ws_rpc import WSRPCClient, WebSocketError, normalize_ws_url

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"

AUTH_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "prime"
AUTH_FILE = AUTH_DIR / "auth.json"

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
CYN = "\033[96m"
DIM = "\033[2m"
BLD = "\033[1m"


def disable_color() -> None:
    global R, GRN, YLW, RED, CYN, DIM, BLD
    R = ""
    GRN = ""
    YLW = ""
    RED = ""
    CYN = ""
    DIM = ""
    BLD = ""


def ok(msg: str) -> None:
    print(f"{GRN}✓{R} {msg}")


def warn(msg: str) -> None:
    print(f"{YLW}!{R} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{R} {msg}")


def info(msg: str) -> None:
    print(f"{CYN}→{R} {msg}")


def _load_auth() -> dict[str, Any] | None:
    if not AUTH_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _resolve_gateway_url(args: argparse.Namespace) -> tuple[str, bool]:
    """Return (ws_url, url_was_explicitly_set)."""
    url = getattr(args, "url", None)
    if url:
        return normalize_ws_url(url), True

    env_url = (os.getenv("PRIME_GATEWAY_URL") or "").strip()
    if env_url:
        return normalize_ws_url(env_url), False

    auth = _load_auth() or {}
    base_url = (auth.get("base_url") or "").strip()
    if base_url:
        return normalize_ws_url(str(base_url)), False

    # Default to local API URL (HTTP) and normalize to ws(s)://.../api/ws/events.
    return normalize_ws_url(os.getenv("PRIME_API_URL", "http://localhost:8000")), False


def _resolve_credentials(args: argparse.Namespace, *, url_explicit: bool) -> tuple[str | None, str | None]:
    token = (getattr(args, "token", None) or "").strip() or None
    password = (getattr(args, "password", None) or "").strip() or None
    if token or password:
        return token, password

    if url_explicit:
        raise ValueError("When --url is set, you must pass --token or --password (no config fallback).")

    auth = _load_auth() or {}
    token = (auth.get("access_token") or "").strip() or None
    if token:
        return token, None

    raise ValueError("No credentials found. Run: prime auth login (or pass --token/--password).")


def _json_print(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=True, indent=2))


def _dc(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]
    kwargs: dict[str, Any] = {"check": False}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def _parse_compose_ps(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _systemd_unit_snapshot(*, deep: bool) -> dict[str, Any]:
    """Best-effort snapshot of systemd unit state (user + optionally system)."""
    unit = "prime-gateway"
    result: dict[str, Any] = {"unit": unit, "systemctl": bool(_which("systemctl"))}
    if not result["systemctl"]:
        return result

    def run(args: list[str]) -> tuple[int, str]:
        r = subprocess.run(args, capture_output=True, text=True, check=False)
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode, out

    code, out = run(["systemctl", "--user", "is-active", unit])
    result["user_active"] = out or ("active" if code == 0 else "unknown")
    code, out = run(["systemctl", "--user", "is-enabled", unit])
    result["user_enabled"] = out or ("enabled" if code == 0 else "unknown")

    if deep:
        code, out = run(["systemctl", "is-active", unit])
        result["system_active"] = out or ("active" if code == 0 else "unknown")
        code, out = run(["systemctl", "is-enabled", unit])
        result["system_enabled"] = out or ("enabled" if code == 0 else "unknown")

    return result


def _which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def _rpc_probe(
    *,
    url: str,
    token: str | None,
    password: str | None,
    timeout_ms: int,
) -> tuple[bool, dict[str, Any] | str]:
    t0 = time.monotonic()
    client = WSRPCClient(
        url=url,
        token=token,
        password=password,
        timeout_ms=timeout_ms,
        platform=sys.platform,
    )
    try:
        client.connect()
        payload = client.request("status", {})
        dt_ms = int((time.monotonic() - t0) * 1000)
        return True, {"latency_ms": dt_ms, "payload": payload}
    except Exception as exc:
        return False, str(exc)
    finally:
        client.shutdown()


def cmd_health(args: argparse.Namespace) -> int:
    if getattr(args, "timeout", None) is None:
        args.timeout = 10_000
    ws_url, url_explicit = _resolve_gateway_url(args)
    token, password = _resolve_credentials(args, url_explicit=url_explicit)

    client = WSRPCClient(
        url=ws_url,
        token=token,
        password=password,
        timeout_ms=args.timeout,
        platform=sys.platform,
    )
    try:
        client.connect()
        payload = client.request("health.get", {})
    finally:
        client.shutdown()

    if getattr(args, "json", False):
        _json_print(payload)
        return 0

    print(f"{BLD}Prime Gateway Health{R}")
    print(f"{DIM}{'-' * 54}{R}")
    ok(f"WS: {ws_url}")
    ok(f"health.get: {payload.get('status', 'ok')}")
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    if getattr(args, "timeout", None) is None:
        args.timeout = 10_000
    ws_url, url_explicit = _resolve_gateway_url(args)
    token, password = _resolve_credentials(args, url_explicit=url_explicit)

    params: dict[str, Any] = {}
    if args.params:
        try:
            parsed = json.loads(args.params)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON for --params: {exc}", file=sys.stderr)
            return 2
        if isinstance(parsed, dict):
            params = parsed
        else:
            params = {"value": parsed}

    client = WSRPCClient(
        url=ws_url,
        token=token,
        password=password,
        timeout_ms=args.timeout,
        platform=sys.platform,
    )
    try:
        client.connect()
        payload = client.request(args.method, params, expect_final=bool(args.expect_final))
    finally:
        client.shutdown()

    if getattr(args, "json", False):
        _json_print(payload)
        return 0

    print(f"{BLD}Gateway Call{R}")
    print(f"{DIM}{'-' * 54}{R}")
    print(f"method: {args.method}")
    print(f"url:    {ws_url}")
    print("")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if getattr(args, "timeout", None) is None:
        args.timeout = 10_000
    ws_url, url_explicit = _resolve_gateway_url(args)
    token = password = None
    if not args.no_probe:
        token, password = _resolve_credentials(args, url_explicit=url_explicit)

    docker_snapshot: dict[str, Any] = {"ok": False}
    compose_ps = _dc("ps", "--format", "json", capture=True)
    if compose_ps.returncode == 0:
        docker_snapshot["ok"] = True
        docker_snapshot["services"] = _parse_compose_ps(compose_ps.stdout or "")
    else:
        docker_snapshot["error"] = (compose_ps.stderr or "").strip() or "docker compose ps failed"

    systemd_snapshot = _systemd_unit_snapshot(deep=bool(args.deep))

    probe_ok = None
    probe_detail: dict[str, Any] | str | None = None
    if not args.no_probe:
        probe_ok, probe_detail = _rpc_probe(
            url=ws_url,
            token=token,
            password=password,
            timeout_ms=args.timeout,
        )

    payload: dict[str, Any] = {
        "service": {
            "docker": docker_snapshot,
            "systemd": systemd_snapshot,
        },
        "probe": None if args.no_probe else {"ok": bool(probe_ok), "detail": probe_detail},
    }

    if getattr(args, "json", False):
        _json_print(payload)
        return 0 if (args.no_probe or probe_ok) else 1

    print(f"{BLD}Prime Gateway Status{R}")
    print(f"{DIM}{'-' * 54}{R}")

    if docker_snapshot.get("ok"):
        services = docker_snapshot.get("services") or []
        running = 0
        for svc in services:
            state = str(svc.get("State", "")).lower()
            if state == "running":
                running += 1
        ok(f"Docker services: {running}/{len(services)} running")
    else:
        warn(f"Docker: {docker_snapshot.get('error', 'unavailable')}")

    if systemd_snapshot.get("systemctl"):
        ok(f"systemd --user: active={systemd_snapshot.get('user_active')}, enabled={systemd_snapshot.get('user_enabled')}")
        if args.deep:
            ok(
                "systemd (system): "
                f"active={systemd_snapshot.get('system_active')}, enabled={systemd_snapshot.get('system_enabled')}"
            )
    else:
        warn("systemctl not found")

    if args.no_probe:
        info("Probe skipped (--no-probe)")
        return 0

    if probe_ok:
        detail = probe_detail if isinstance(probe_detail, dict) else {}
        ok(f"WS probe: ok ({detail.get('latency_ms', '?')}ms) {ws_url}")
        return 0

    fail(f"WS probe failed: {probe_detail}")
    return 1


def cmd_discover(args: argparse.Namespace) -> int:
    if getattr(args, "timeout", None) is None:
        args.timeout = 2_000
    payload = {
        "ok": False,
        "error": "gateway discovery is not implemented yet (needs mDNS/Bonjour)",
        "timeout_ms": int(args.timeout),
    }
    if getattr(args, "json", False):
        _json_print(payload)
    else:
        fail(payload["error"])
    return 1


def cmd_probe(_: argparse.Namespace) -> int:
    print("gateway probe is not implemented yet (SSH + multi-target probing).")
    return 1


def cmd_unimplemented(args: argparse.Namespace) -> int:
    print(f"{args.subcommand} is not implemented yet. Use: prime start / prime status / prime logs")
    return 1


def build_parser() -> argparse.ArgumentParser:
    def add_shared(p: argparse.ArgumentParser) -> None:
        # OpenClaw examples put flags after the subcommand, so we add shared flags to both the
        # main parser and each subparser. Use SUPPRESS defaults to avoid overriding values that
        # were already parsed earlier.
        p.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS, help="Disable ANSI colors")
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON output")
        p.add_argument("--url", default=argparse.SUPPRESS, help="Gateway WebSocket URL (ws://... or https://...)")
        p.add_argument("--token", default=argparse.SUPPRESS, help="Gateway auth token (JWT)")
        p.add_argument("--password", default=argparse.SUPPRESS, help="Gateway password (if enabled)")
        p.add_argument(
            "--timeout",
            type=int,
            default=argparse.SUPPRESS,
            help="Timeout budget in milliseconds (defaults vary by subcommand)",
        )

    parser = argparse.ArgumentParser(prog="prime gateway", description="Prime Gateway CLI (OpenClaw-compatible)")
    add_shared(parser)

    sub = parser.add_subparsers(dest="subcommand", required=False)

    p_health = sub.add_parser("health", help="Gateway health check (WS RPC)")
    add_shared(p_health)
    p_health.set_defaults(func=cmd_health)

    p_status = sub.add_parser("status", help="Gateway service status + optional WS probe")
    add_shared(p_status)
    p_status.add_argument("--no-probe", action="store_true", help="Skip WS probe")
    p_status.add_argument("--deep", action="store_true", help="Scan system-level services too")
    p_status.set_defaults(func=cmd_status)

    p_call = sub.add_parser("call", help="Call a WS RPC method")
    add_shared(p_call)
    p_call.add_argument("method", help="RPC method (e.g. status, health.get, config.get)")
    p_call.add_argument("--params", default="", help="JSON params object (default: {})")
    p_call.add_argument("--expect-final", action="store_true", help="Wait for final response (when supported)")
    p_call.set_defaults(func=cmd_call)

    p_discover = sub.add_parser("discover", help="Discover gateways on LAN via mDNS/Bonjour")
    add_shared(p_discover)
    p_discover.set_defaults(func=cmd_discover)

    p_probe = sub.add_parser("probe", help="Probe gateways (local, remote, SSH)")
    add_shared(p_probe)
    p_probe.set_defaults(func=cmd_probe)

    # Service lifecycle (stubs for now; implemented later for full OpenClaw parity).
    for name in ("run", "install", "start", "stop", "restart", "uninstall"):
        p = sub.add_parser(name, help=f"{name} (not implemented yet)")
        add_shared(p)
        p.set_defaults(func=cmd_unimplemented)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "no_color", False) or os.getenv("NO_COLOR") or not sys.stdout.isatty():
        disable_color()

    if not args.subcommand:
        # OpenClaw-compatible: `openclaw gateway` defaults to `run`.
        args.subcommand = "run"
        args.func = cmd_unimplemented

    try:
        return int(args.func(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except WebSocketError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
