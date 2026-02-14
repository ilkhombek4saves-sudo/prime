"""
Doctor API — deep health diagnostics for Prime.
GET /api/doctor        — run all checks
GET /api/doctor/quick  — lightweight subset (no DB I/O)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.persistence.models import User

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _check(label: str, ok: bool, detail: str = "", fix: str = "") -> dict:
    return {"label": label, "ok": ok, "detail": detail, "fix": fix}


def _run_checks(quick: bool = False) -> list[dict]:
    results = []

    # 1 — Python version
    py = sys.version_info
    results.append(_check(
        "python_version",
        py >= (3, 10),
        f"Python {py.major}.{py.minor}.{py.micro}",
        "Upgrade to Python 3.10+",
    ))

    # 2 — Database connectivity
    if not quick:
        try:
            from app.persistence.database import engine
            import sqlalchemy
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            results.append(_check("database", True, "Connected"))
        except Exception as exc:
            results.append(_check("database", False, str(exc), "Check DATABASE_URL and DB service"))

    # 3 — Environment variables
    from app.config.settings import get_settings
    s = get_settings()
    results.append(_check(
        "secret_key",
        s.secret_key not in ("change-me", "secret", "") and len(s.secret_key) >= 16,
        "OK" if len(s.secret_key) >= 16 else "Too short or default",
        "Set SECRET_KEY to a 32+ char random string",
    ))
    results.append(_check(
        "jwt_secret",
        s.jwt_secret not in ("change-me-too", "secret", ""),
        "OK" if s.jwt_secret not in ("change-me-too", "secret", "") else "Default value",
        "Set JWT_SECRET to a random 32+ char string",
    ))

    # 4 — Provider API keys
    providers_ok = 0
    for env_var in ("OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"):
        if os.getenv(env_var, ""):
            providers_ok += 1
    results.append(_check(
        "provider_keys",
        providers_ok > 0,
        f"{providers_ok} provider key(s) configured",
        "Set at least one of OPENAI_API_KEY, ANTHROPIC_AUTH_TOKEN, DEEPSEEK_API_KEY",
    ))

    # 5 — Docker socket (for sandbox)
    docker_sock = os.path.exists("/var/run/docker.sock")
    results.append(_check(
        "docker_socket",
        docker_sock,
        "/var/run/docker.sock found" if docker_sock else "Not found",
        "Mount docker socket in docker-compose.yml",
    ))

    # 6 — Docker CLI binary
    docker_bin = shutil.which("docker") is not None
    results.append(_check(
        "docker_binary",
        docker_bin,
        "docker found" if docker_bin else "Not in PATH",
        "Install Docker or ensure it's in PATH",
    ))

    # 7 — Tailscale
    ts_bin = shutil.which("tailscale") is not None
    results.append(_check(
        "tailscale",
        ts_bin,
        "tailscale found" if ts_bin else "Not installed (optional)",
        "Install tailscale for public HTTPS tunnels (optional)",
    ))

    # 8 — Browser bridge
    import httpx
    browser_ok = False
    browser_detail = "Not running"
    try:
        r = httpx.get("http://localhost:3001/health", timeout=1.5)
        browser_ok = r.status_code == 200
        browser_detail = "Running on :3001" if browser_ok else f"HTTP {r.status_code}"
    except (httpx.HTTPError, OSError):
        browser_detail = "Not running (optional)"
    results.append(_check(
        "browser_bridge",
        browser_ok,
        browser_detail,
        "Run `docker compose up browser-bridge` or start browser/server.js",
    ))

    # 9 — Workspace dir
    workspace = getattr(s, "workspace_root", "/tmp/prime-workspace")
    ws_ok = os.path.isdir(workspace) or workspace == ""
    results.append(_check(
        "workspace",
        True,  # Non-fatal
        workspace,
        "",
    ))

    # 10 — Migration state
    if not quick:
        try:
            from app.persistence.database import engine
            import sqlalchemy
            with engine.connect() as conn:
                result = conn.execute(sqlalchemy.text(
                    "SELECT version_num FROM alembic_version LIMIT 1"
                ))
                row = result.fetchone()
                ver = row[0] if row else "unknown"
            results.append(_check("migrations", True, f"Latest migration: {ver}"))
        except Exception as exc:
            results.append(_check(
                "migrations", False, str(exc),
                "Run `alembic upgrade head` inside backend/",
            ))

    # 11 — Node.js (for browser bridge)
    node_bin = shutil.which("node") is not None
    results.append(_check(
        "nodejs",
        node_bin,
        "node found" if node_bin else "Not installed (optional)",
        "Install Node.js 18+ for browser automation",
    ))

    # 12 — Gateway lock file
    lock_path = getattr(s, "gateway_lock_path", "/tmp/prime-gateway.lock")
    lock_held = os.path.exists(lock_path)
    results.append(_check(
        "gateway_lock",
        True,
        f"Lock: {lock_path} ({'held' if lock_held else 'free'})",
        "",
    ))

    return results


@router.get("")
def run_doctor(current_user: User = Depends(get_current_user)):
    """Run full diagnostic suite."""
    started = datetime.now(timezone.utc)
    checks = _run_checks(quick=False)
    passed = sum(1 for c in checks if c["ok"])
    failed = [c for c in checks if not c["ok"]]
    return {
        "timestamp": started.isoformat(),
        "passed": passed,
        "failed": len(failed),
        "total": len(checks),
        "healthy": len(failed) == 0,
        "checks": checks,
    }


@router.get("/quick")
def run_doctor_quick(current_user: User = Depends(get_current_user)):
    """Run lightweight diagnostic checks (no DB I/O)."""
    checks = _run_checks(quick=True)
    passed = sum(1 for c in checks if c["ok"])
    return {
        "passed": passed,
        "total": len(checks),
        "healthy": all(c["ok"] for c in checks),
        "checks": checks,
    }


@router.post("/repair")
def run_repair(current_user: User = Depends(get_current_user)):
    """Attempt auto-repair for known issues."""
    repaired = []

    # 1 — Ensure config directory exists
    config_dir = Path("config")
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        repaired.append("Created config/ directory")

    # 2 — Ensure workspace directory exists
    from app.config.settings import get_settings
    s = get_settings()
    workspace = getattr(s, "workspace_root", "/tmp/prime-workspace")
    if workspace and not os.path.exists(workspace):
        os.makedirs(workspace, exist_ok=True)
        repaired.append(f"Created workspace directory: {workspace}")

    # 3 — Run migrations if possible
    try:
        from app.persistence.database import engine
        import sqlalchemy
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        # DB is up — try alembic
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            repaired.append("Ran alembic migrations")
        else:
            repaired.append(f"Migration attempt: {result.stderr[:200]}")
    except Exception as exc:
        repaired.append(f"Migration skipped: {exc}")

    # 4 — Validate config
    try:
        from app.services.config_loader import ConfigLoader
        ConfigLoader().load_and_validate()
        repaired.append("Config validation passed")
    except Exception as exc:
        repaired.append(f"Config validation: {exc}")

    return {
        "repaired": len(repaired),
        "actions": repaired,
    }
