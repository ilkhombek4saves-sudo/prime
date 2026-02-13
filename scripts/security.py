#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.security_audit import SecurityAuditor  # noqa: E402

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
BLU = "\033[94m"
DIM = "\033[2m"
BLD = "\033[1m"


def _use_color(args: argparse.Namespace) -> bool:
    if args.no_color:
        return False
    return sys.stdout.isatty()


def _c(value: str, color: str, enabled: bool) -> str:
    return f"{color}{value}{R}" if enabled else value


def _marker(severity: str) -> str:
    if severity == "critical":
        return "✗"
    if severity == "warning":
        return "!"
    return "i"


def _severity_color(severity: str) -> str:
    if severity == "critical":
        return RED
    if severity == "warning":
        return YLW
    return BLU


def _posix_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except Exception:
        return None


def _is_world_readable(mode: int) -> bool:
    return bool(mode & stat.S_IROTH)


def _is_group_readable(mode: int) -> bool:
    return bool(mode & stat.S_IRGRP)


def _chmod_600(path: Path) -> bool:
    try:
        os.chmod(path, 0o600)
        return True
    except Exception:
        return False


def _chmod_700(path: Path) -> bool:
    try:
        os.chmod(path, 0o700)
        return True
    except Exception:
        return False


def _audit_local_files() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    env_file = ROOT / ".env"
    if env_file.exists():
        mode = _posix_mode(env_file)
        if mode is not None and (_is_group_readable(mode) or _is_world_readable(mode)):
            findings.append(
                {
                    "severity": "warning",
                    "code": "ENV_PERMS_OPEN",
                    "message": f".env is readable by group/others (mode {oct(mode)}).",
                    "fix": "Run: chmod 600 .env",
                }
            )

    config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "prime"
    auth_file = config_dir / "auth.json"
    if auth_file.exists():
        mode = _posix_mode(auth_file)
        if mode is not None and (_is_group_readable(mode) or _is_world_readable(mode)):
            findings.append(
                {
                    "severity": "warning",
                    "code": "AUTH_PERMS_OPEN",
                    "message": f"{auth_file} is readable by group/others (mode {oct(mode)}).",
                    "fix": f"Run: chmod 600 {auth_file}",
                }
            )
    if config_dir.exists():
        mode = _posix_mode(config_dir)
        if mode is not None and (mode & 0o077):
            findings.append(
                {
                    "severity": "info",
                    "code": "CONFIG_DIR_PERMS_OPEN",
                    "message": f"{config_dir} is accessible by group/others (mode {oct(mode)}).",
                    "fix": f"Run: chmod 700 {config_dir}",
                }
            )

    return findings


def _apply_fixes(findings: list[dict[str, str]]) -> list[str]:
    actions: list[str] = []
    codes = {f.get("code") for f in findings}

    if "ENV_PERMS_OPEN" in codes:
        env_file = ROOT / ".env"
        if env_file.exists() and _chmod_600(env_file):
            actions.append("chmod 600 .env")

    if "AUTH_PERMS_OPEN" in codes:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "prime"
        auth_file = config_dir / "auth.json"
        if auth_file.exists() and _chmod_600(auth_file):
            actions.append(f"chmod 600 {auth_file}")

    if "CONFIG_DIR_PERMS_OPEN" in codes:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "prime"
        if config_dir.exists() and _chmod_700(config_dir):
            actions.append(f"chmod 700 {config_dir}")

    return actions


def cmd_audit(args: argparse.Namespace) -> int:
    color = _use_color(args)

    report = SecurityAuditor().run().to_dict()
    file_findings = _audit_local_files() if args.deep else []

    findings = list(report.get("findings") or [])
    findings.extend(file_findings)

    passed = int(report.get("passed") or 0)
    failed = len(findings)
    critical = int(report.get("critical") or 0) + sum(1 for f in file_findings if f.get("severity") == "critical")

    payload: dict[str, Any] = {
        "passed": passed,
        "failed": failed,
        "critical": critical,
        "findings": findings,
        "deep": bool(args.deep),
    }

    if args.fix and not args.json:
        actions = _apply_fixes(file_findings)
        if actions:
            print(_c("Applied fixes:", BLD, color))
            for a in actions:
                print(f"- {a}")
            print("")
        # Re-run deep file checks after fixes (auditor checks are env-only).
        file_findings = _audit_local_files() if args.deep else []
        findings = list(report.get("findings") or [])
        findings.extend(file_findings)
        payload["findings"] = findings
        payload["failed"] = len(findings)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0 if failed == 0 else 1

    print(_c("Prime Security Audit", BLD, color))
    print(_c("-" * 54, DIM, color))
    print(f"Passed:   {passed}")
    print(f"Findings: {failed} (critical: {critical})")
    if args.deep:
        print(_c("Mode:     deep", DIM, color))
    print("")

    if not findings:
        print(_c("✓ No issues found", GRN, color))
        return 0

    for f in findings:
        severity = str(f.get("severity") or "info").lower()
        code = str(f.get("code") or "UNKNOWN")
        message = str(f.get("message") or "")
        fix = str(f.get("fix") or "")
        marker = _marker(severity)
        line = f"{marker} {severity.upper():8} {code}: {message}"
        print(_c(line, _severity_color(severity), color))
        if fix:
            print(_c(f"    fix: {fix}", DIM, color))

    return 0 if failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prime security", description="Prime security tooling")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_audit = sub.add_parser("audit", help="Run security audit checks")
    p_audit.add_argument("--json", action="store_true", help="Emit JSON report")
    p_audit.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    p_audit.add_argument(
        "--deep",
        action="store_true",
        help="Include local filesystem permission checks (host-side)",
    )
    p_audit.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe host-side fixes for deep checks (chmod for sensitive files)",
    )
    p_audit.set_defaults(func=cmd_audit)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

