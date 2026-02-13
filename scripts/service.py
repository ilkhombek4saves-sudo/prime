#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_USER_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"
SERVICE_NAME = "prime-gateway"


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), check=check)


def _systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def _service_path() -> Path:
    return SYSTEMD_USER_DIR / f"{SERVICE_NAME}.service"


def _render_service() -> str:
    python = shutil.which("python3") or "python3"
    env_file = ROOT / ".env"
    return f"""[Unit]
Description=Prime Gateway (non-Docker)
After=network.target

[Service]
Type=simple
WorkingDirectory={ROOT}
Environment=PYTHONPATH={ROOT}/backend
EnvironmentFile={env_file}
ExecStart={python} -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
"""


def cmd_install(_: argparse.Namespace) -> int:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    path = _service_path()
    path.write_text(_render_service(), encoding="utf-8")
    print(f"Installed {path}")
    if not _systemctl_available():
        print("systemctl not found; enable/start manually.")
        return 0
    _run("systemctl", "--user", "daemon-reload")
    print("Run: systemctl --user enable --now prime-gateway")
    return 0


def cmd_uninstall(_: argparse.Namespace) -> int:
    path = _service_path()
    if path.exists():
        path.unlink()
        print(f"Removed {path}")
    if _systemctl_available():
        _run("systemctl", "--user", "daemon-reload")
    return 0


def cmd_start(_: argparse.Namespace) -> int:
    if not _systemctl_available():
        print("systemctl not found")
        return 1
    return _run("systemctl", "--user", "start", SERVICE_NAME, check=False).returncode


def cmd_stop(_: argparse.Namespace) -> int:
    if not _systemctl_available():
        print("systemctl not found")
        return 1
    return _run("systemctl", "--user", "stop", SERVICE_NAME, check=False).returncode


def cmd_status(_: argparse.Namespace) -> int:
    if not _systemctl_available():
        print("systemctl not found")
        return 1
    return _run("systemctl", "--user", "status", SERVICE_NAME, check=False).returncode


def cmd_logs(_: argparse.Namespace) -> int:
    if not _systemctl_available():
        print("systemctl not found")
        return 1
    return _run("journalctl", "--user", "-u", SERVICE_NAME, "-f", check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="prime service")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("logs")

    args = parser.parse_args()
    return {
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "logs": cmd_logs,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
