#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"

DEFAULT_API_URL = os.getenv("PRIME_API_URL", "http://localhost:8000").rstrip("/")
DEFAULT_DASHBOARD_URL = os.getenv("PRIME_DASHBOARD_URL", "http://localhost:5173").rstrip("/")
DEFAULT_METRICS_URL = f"{DEFAULT_API_URL}/api/metrics"
DEFAULT_HEALTH_URL = f"{DEFAULT_API_URL}/api/healthz"

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


def dc(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]
    kwargs: dict[str, Any] = {"check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def fetch(url: str, timeout: float = 3.0) -> tuple[bool, dict[str, Any] | str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError:
                payload = body
            return True, payload
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"{exc.reason}"
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def parse_compose_ps(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []

    # docker compose can output either JSON array or JSON line objects
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


def clip_text(value: str, limit: int = 320) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...(truncated)"


def wait_for_health(url: str, timeout_seconds: float, request_timeout: float) -> tuple[bool, str]:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    last_error = "not ready"
    while time.monotonic() < deadline:
        ok_flag, payload = fetch(url, timeout=request_timeout)
        if ok_flag:
            return True, "ok"
        last_error = str(payload)
        time.sleep(0.8)
    return False, last_error


def print_start_summary(args: argparse.Namespace, *, backend_ready: bool, backend_detail: str) -> None:
    print()
    print(f"{BLD}Prime Gateway Ready{R}")
    print(f"{DIM}{'-' * 54}{R}")
    if backend_ready:
        ok(f"Backend health: {args.health_url}")
    else:
        fail(f"Backend health: {args.health_url} ({backend_detail})")
    print(f"Dashboard: {args.dashboard_url}")
    print(f"API docs:  {args.api_url}/docs")
    print(f"WS:        {args.api_url}/api/ws/events")
    print()
    print("Next commands:")
    print("  prime gateway status --watch")
    print("  prime channels doctor --verify-api")
    print("  prime logs backend")


def _run_status_once(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "docker": {"ok": False, "services": []},
        "api": {"ok": False, "url": args.health_url},
        "metrics": {"ok": False, "url": args.metrics_url},
        "dashboard": {"ok": False, "url": args.dashboard_url},
    }
    all_ok = True

    ps = dc("ps", "--format", "json", capture=True, check=False)
    if ps.returncode != 0:
        all_ok = False
        payload["docker"]["error"] = (ps.stderr or "").strip() or "docker compose ps failed"
    else:
        services_raw = parse_compose_ps(ps.stdout or "")
        services = []
        for svc in services_raw:
            services.append(
                {
                    "service": svc.get("Service") or svc.get("Name", "?"),
                    "name": svc.get("Name") or svc.get("Names") or "?",
                    "state": svc.get("State", "unknown"),
                    "status": svc.get("Status", "unknown"),
                    "health": svc.get("Health") or "",
                    "ports": svc.get("Ports") or "",
                }
            )
        payload["docker"]["ok"] = True
        payload["docker"]["services"] = services
        if services:
            running = 0
            for svc in services:
                state = str(svc.get("state") or "").lower()
                if state == "running":
                    running += 1
            payload["docker"]["running"] = running
            payload["docker"]["total"] = len(services)
            if running < len(services):
                all_ok = False
        else:
            all_ok = False

    api_ok, api_body = fetch(args.health_url, timeout=args.timeout)
    payload["api"]["ok"] = api_ok
    payload["api"]["body"] = api_body
    if not api_ok:
        all_ok = False

    metrics_ok, metrics_body = fetch(args.metrics_url, timeout=args.timeout)
    payload["metrics"]["ok"] = metrics_ok
    payload["metrics"]["body"] = clip_text(metrics_body, 320) if isinstance(metrics_body, str) else "<json>"
    if not metrics_ok:
        all_ok = False

    dashboard_ok, dashboard_body = fetch(args.dashboard_url, timeout=args.timeout)
    payload["dashboard"]["ok"] = dashboard_ok
    payload["dashboard"]["body"] = (
        clip_text(dashboard_body, 240) if isinstance(dashboard_body, str) else "<json>"
    )
    if not dashboard_ok:
        all_ok = False

    if args.json:
        payload["ok"] = all_ok
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(f"{BLD}Prime Gateway Status{R}")
        print(f"{DIM}{'-' * 54}{R}")

        if payload["docker"]["ok"]:
            services = payload["docker"].get("services", [])
            running = int(payload["docker"].get("running", 0))
            total = int(payload["docker"].get("total", 0))
            if services and running == total:
                ok(f"Docker services: {running}/{total} running")
            else:
                warn(f"Docker services: {running}/{total} running")
                for svc in services:
                    service = svc.get("service", "?")
                    state = svc.get("state", "?")
                    health = svc.get("health")
                    health_suffix = f", {health}" if health else ""
                    marker = ok if str(state).lower() == "running" else warn
                    marker(f"{service}: {state}{health_suffix}")
        else:
            fail(f"Docker: {payload['docker'].get('error', 'unavailable')}")

        if payload["api"]["ok"]:
            ok(f"API health: {args.health_url}")
        else:
            fail(f"API health: {args.health_url} ({payload['api']['body']})")

        if payload["metrics"]["ok"]:
            ok(f"Metrics: {args.metrics_url}")
        else:
            warn(f"Metrics: {args.metrics_url} ({payload['metrics']['body']})")

        if payload["dashboard"]["ok"]:
            ok(f"Dashboard: {args.dashboard_url}")
        else:
            warn(f"Dashboard: {args.dashboard_url} ({payload['dashboard']['body']})")

    return 0 if (all_ok or not args.strict) else 1


def cmd_status(args: argparse.Namespace) -> int:
    if not args.watch:
        return _run_status_once(args)

    last_code = 0
    try:
        while True:
            if not args.json:
                # Clear screen for a compact "live dashboard" effect in terminal.
                print("\033[2J\033[H", end="")
                print(f"{DIM}Live mode: refresh every {args.interval:.1f}s (Ctrl+C to stop){R}")
            last_code = _run_status_once(args)
            time.sleep(max(0.5, float(args.interval)))
    except KeyboardInterrupt:
        if not args.json:
            print()
            info("Stopped live status mode")
        return last_code


def cmd_start(args: argparse.Namespace) -> int:
    info("Starting gateway services...")
    cmd = ["up", "-d"]
    if args.build:
        cmd.append("--build")
    result = dc(*cmd, check=False)
    if result.returncode != 0:
        fail("Gateway start failed")
        return result.returncode

    ok("Gateway services started")

    if args.no_wait:
        info("Skipping readiness wait (--no-wait)")
        print_start_summary(args, backend_ready=False, backend_detail="readiness wait skipped")
        return 0

    info(f"Waiting for backend readiness ({args.wait_timeout:.0f}s timeout)...")
    backend_ready, backend_detail = wait_for_health(
        args.health_url,
        timeout_seconds=args.wait_timeout,
        request_timeout=args.timeout,
    )
    if backend_ready:
        ok("Backend is healthy")
    else:
        fail("Backend did not become healthy in time")

    if args.post_status:
        _run_status_once(
            argparse.Namespace(
                **{
                    **vars(args),
                    "watch": False,
                    "json": False,
                    "strict": False,
                    "interval": 2.0,
                }
            )
        )
    print_start_summary(args, backend_ready=backend_ready, backend_detail=backend_detail)
    return 0 if backend_ready else 1


def cmd_stop(args: argparse.Namespace) -> int:
    info("Stopping gateway services...")
    result = dc("down", check=False)
    if result.returncode == 0:
        ok("Gateway services stopped")
        return 0
    fail("Gateway stop failed")
    return result.returncode


def cmd_restart(args: argparse.Namespace) -> int:
    service = args.service or "backend"
    info(f"Restarting service: {service}")
    result = dc("restart", service, check=False)
    if result.returncode == 0:
        ok(f"{service} restarted")
        return 0
    fail(f"{service} restart failed")
    return result.returncode


def cmd_logs(args: argparse.Namespace) -> int:
    service = args.service or "backend"
    return dc("logs", "-f", service, check=False).returncode


def cmd_url(args: argparse.Namespace) -> int:
    print(f"Dashboard: {args.dashboard_url}")
    print(f"API:       {args.api_url}")
    print(f"Health:    {args.health_url}")
    print(f"Metrics:   {args.metrics_url}")
    print(f"Docs:      {args.api_url}/docs")
    print(f"WS:        {args.api_url}/api/ws/events")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    print(args.dashboard_url)
    if args.open:
        opened = webbrowser.open(args.dashboard_url)
        if opened:
            ok("Dashboard opened in browser")
            return 0
        warn("Could not auto-open browser. Open URL manually.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prime gateway control commands")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--metrics-url", default=DEFAULT_METRICS_URL)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="Show gateway/runtime status")
    p_status.add_argument("--json", action="store_true", help="Emit JSON status report")
    p_status.add_argument("--strict", action="store_true", help="Return non-zero if anything unhealthy")
    p_status.add_argument("--watch", action="store_true", help="Refresh continuously in terminal")
    p_status.add_argument("--interval", type=float, default=2.0, help="Watch refresh interval (seconds)")
    p_status.set_defaults(func=cmd_status)

    p_start = sub.add_parser("start", help="Start gateway services")
    p_start.add_argument("--build", action="store_true", help="Build images before start")
    p_start.add_argument("--no-wait", action="store_true", help="Do not wait for health readiness")
    p_start.add_argument("--wait-timeout", type=float, default=45.0, help="Health wait timeout (seconds)")
    p_start.add_argument("--post-status", action="store_true", help="Print full status block after start")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop gateway services")
    p_stop.set_defaults(func=cmd_stop)

    p_restart = sub.add_parser("restart", help="Restart service (default backend)")
    p_restart.add_argument("service", nargs="?", default="backend")
    p_restart.set_defaults(func=cmd_restart)

    p_logs = sub.add_parser("logs", help="Tail service logs")
    p_logs.add_argument("service", nargs="?", default="backend")
    p_logs.set_defaults(func=cmd_logs)

    p_health = sub.add_parser("health", help="Alias of status --strict")
    p_health.add_argument("--json", action="store_true", help="Emit JSON status report")
    p_health.add_argument("--watch", action="store_true", help="Refresh continuously in terminal")
    p_health.add_argument("--interval", type=float, default=2.0, help="Watch refresh interval (seconds)")
    p_health.set_defaults(
        func=lambda args: cmd_status(
            argparse.Namespace(
                **{
                    **vars(args),
                    "strict": True,
                }
            )
        )
    )

    p_url = sub.add_parser("url", help="Print dashboard/API URLs")
    p_url.set_defaults(func=cmd_url)

    p_dash = sub.add_parser("dashboard", help="Print dashboard URL")
    p_dash.add_argument("--open", action="store_true", help="Open dashboard in browser")
    p_dash.set_defaults(func=cmd_dashboard)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.no_color or not sys.stdout.isatty():
        disable_color()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
