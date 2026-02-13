#!/usr/bin/env python3
"""
Prime — Full Onboarding Automation

Usage:
  python scripts/onboard.py                  # interactive setup
  python scripts/onboard.py --auto           # non-interactive (env vars only)
  python scripts/onboard.py --prod           # production mode (Caddy + TLS)
  python scripts/onboard.py --doctor         # health + connectivity check
  python scripts/onboard.py --repair         # migrations + config sync
  python scripts/onboard.py --seed           # seed demo data
  python scripts/onboard.py --validate       # validate keys only
  python scripts/onboard.py --auto --prod    # auto onboarding in prod mode
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from getpass import getpass
from pathlib import Path

if sys.version_info < (3, 10):
    print("ERROR: Python 3.10+ is required.")
    sys.exit(1)

ROOT     = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

R    = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
RED  = "\033[91m"
GRN  = "\033[92m"
YLW  = "\033[93m"
BLU  = "\033[94m"
MAG  = "\033[95m"
CYN  = "\033[96m"
WHT  = "\033[97m"

def ok(msg: str)   -> None: print(f"  {GRN}✓{R}  {msg}")
def warn(msg: str) -> None: print(f"  {YLW}!{R}  {msg}")
def fail(msg: str) -> None: print(f"  {RED}✗{R}  {msg}")
def info(msg: str) -> None: print(f"  {BLU}→{R}  {msg}")
def hr(w: int = 58) -> None: print(f"{DIM}{'─' * w}{R}")

def step(n: int, total: int, title: str) -> None:
    print()
    print(f"{BOLD}{CYN}  Step {n}/{total}:{R} {BOLD}{title}{R}")
    hr()

def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    hint = f" {DIM}[{default}]{R}" if default else ""
    full = f"  {WHT}{prompt}{hint}: {R}"
    val = getpass(full) if secret else input(full)
    return val.strip() or default

def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    val = input(f"  {WHT}{prompt}{R} {DIM}[{hint}]{R}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")

def banner() -> None:
    print()
    print(f"{BOLD}{CYN} ██████╗ ██████╗ ██╗███╗   ███╗███████╗{R}")
    print(f"{BOLD}{CYN} ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝{R}")
    print(f"{BOLD}{CYN} ██████╔╝██████╔╝██║██╔████╔██║█████╗  {R}")
    print(f"{BOLD}{CYN} ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  {R}")
    print(f"{BOLD}{CYN} ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗{R}")
    print(f"{BOLD}{CYN} ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝{R}")
    print()
    print(f" {DIM}Prime — AI Agent Platform  ·  Full Onboarding Automation{R}")
    print()

# ── .env ─────────────────────────────────────────────────────────────────────

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

def save_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    written: set[str] = set()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    lines.append(f"{k}={updates[k]}")
                    written.add(k)
                    continue
            lines.append(line)
    for k, v in updates.items():
        if k not in written:
            lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n")

def generate_env_from_example() -> dict[str, str]:
    """Generate .env from .env.example, auto-filling secrets and using env vars."""
    env: dict[str, str] = {}
    if ENV_EXAMPLE.exists():
        for line in ENV_EXAMPLE.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                k = k.strip()
                env_val = os.getenv(k)
                if env_val:
                    env[k] = env_val
                elif v.strip() and "CHANGE_ME" not in v:
                    env[k] = v.strip()
    # Auto-generate secrets
    for key in ("SECRET_KEY", "JWT_SECRET"):
        if not env.get(key) or "CHANGE_ME" in env.get(key, ""):
            env[key] = secrets.token_hex(32)
    if not env.get("DB_PASSWORD") or "CHANGE_ME" in env.get("DB_PASSWORD", ""):
        db_pass = secrets.token_hex(16)
        env["DB_PASSWORD"] = db_pass
        env["DATABASE_URL"] = f"postgresql+psycopg://postgres:{db_pass}@db:5432/multibot"
    if not env.get("DATABASE_URL"):
        env["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@db:5432/multibot"
    if not env.get("APP_ENV"):
        env["APP_ENV"] = "dev"
    return env

# ── docker compose ───────────────────────────────────────────────────────────

def dc(*args: str, capture: bool = False, check: bool = True, prod: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose"]
    if prod and (ROOT / "docker-compose.prod.yml").exists():
        cmd += ["-f", str(ROOT / "docker-compose.prod.yml")]
    else:
        cmd += ["-f", str(ROOT / "docker-compose.yml")]
    cmd += list(args)
    kwargs: dict = {"cwd": str(ROOT), "check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)

def dc_exec(service: str, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "exec"]
    if env_extra:
        for k, v in env_extra.items():
            cmd += ["-e", f"{k}={v}"]
    cmd += [service] + list(args)
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

# ── Validation ───────────────────────────────────────────────────────────────

def validate_telegram_token(token: str) -> tuple[bool, str]:
    """Call Telegram getMe to validate bot token. Returns (ok, bot_username_or_error)."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                bot_info = data.get("result", {})
                username = bot_info.get("username", "unknown")
                return True, f"@{username}"
            return False, data.get("description", "unknown error")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "Invalid token (401 Unauthorized)"
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

def validate_provider_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Quick validation of provider API key. Returns (ok, detail)."""
    if not api_key:
        return False, "no key"

    endpoints = {
        "openai":    ("https://api.openai.com/v1/models", "Bearer"),
        "deepseek":  ("https://api.deepseek.com/v1/models", "Bearer"),
        "kimi":      ("https://api.moonshot.cn/v1/models", "Bearer"),
        "anthropic": ("https://api.anthropic.com/v1/messages", "x-api-key"),
        "mistral":   ("https://api.mistral.ai/v1/models", "Bearer"),
        "gemini":    (f"https://generativelanguage.googleapis.com/v1/models?key={api_key}", None),
    }

    endpoint_info = endpoints.get(provider.lower())
    if not endpoint_info:
        return True, "skipped (unknown provider)"

    url, auth_type = endpoint_info

    try:
        headers = {"Content-Type": "application/json"}
        if auth_type == "Bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "x-api-key":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"

        if provider.lower() == "anthropic":
            data = json.dumps({
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            }).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        else:
            req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, "valid"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "invalid key (401)"
        if exc.code == 402:
            return True, "valid (billing issue)"
        if exc.code == 429:
            return True, "valid (rate limited)"
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, f"unreachable: {exc}"

def validate_all_tokens(env: dict[str, str]) -> None:
    """Validate Telegram and provider keys from .env."""
    print()
    print(f"{BOLD}  Key Validation{R}")
    hr()

    # Telegram
    tokens = [t.strip() for t in env.get("TELEGRAM_BOT_TOKENS", "").split(",") if t.strip()]
    for token in tokens:
        valid, detail = validate_telegram_token(token)
        if valid:
            ok(f"Telegram bot: {detail}")
        else:
            fail(f"Telegram bot: {detail}")

    if not tokens:
        warn("No Telegram bot tokens configured")

    # Providers
    provider_keys = [
        ("OpenAI",    "OPENAI_API_KEY",       "openai"),
        ("Anthropic", "ANTHROPIC_AUTH_TOKEN",  "anthropic"),
        ("DeepSeek",  "DEEPSEEK_API_KEY",     "deepseek"),
        ("Kimi",      "KIMI_API_KEY",         "kimi"),
        ("Mistral",   "MISTRAL_API_KEY",      "mistral"),
        ("Gemini",    "GEMINI_API_KEY",        "gemini"),
        ("GLM/Z.AI",  "ZAI_API_KEY",          "glm"),
        ("Qwen",      "QWEN_API_KEY",         "qwen"),
    ]

    any_valid = False
    for label, env_key, provider_id in provider_keys:
        key = env.get(env_key, "")
        if not key:
            continue
        valid, detail = validate_provider_key(provider_id, key)
        if valid:
            ok(f"{label}: {detail}")
            any_valid = True
        else:
            fail(f"{label}: {detail}")

    if not any_valid and not any(env.get(k) for _, k, _ in provider_keys):
        warn("No AI provider keys configured — agents won't respond (unless you use local Ollama)")

# ── Step implementations ────────────────────────────────────────────────────

def check_prereqs() -> bool:
    all_ok = True
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if r.returncode == 0:
        ok("Docker is running")
    else:
        fail("Docker is not running")
        all_ok = False

    r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if r.returncode == 0:
        ver = r.stdout.strip().split("version")[-1].strip()
        ok(f"Docker Compose {ver}")
    else:
        fail("docker compose not found")
        all_ok = False
    return all_ok

def setup_env(env: dict[str, str]) -> dict[str, str]:
    changed = False
    for key in ("SECRET_KEY", "JWT_SECRET"):
        if not env.get(key) or env[key] in ("replace_me", "replace_me_too", "change-me", "change-me-too", ""):
            env[key] = secrets.token_hex(32)
            ok(f"Generated {key}")
            changed = True
        else:
            ok(f"{key} already set")
    if not env.get("DATABASE_URL"):
        env["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@db:5432/multibot"
    if not env.get("APP_ENV"):
        env["APP_ENV"] = "dev"
    if not env.get("APP_PORT"):
        env["APP_PORT"] = "8000"
    if changed:
        save_env(env)
        ok("Saved to .env")
    return env

def configure_providers(env: dict[str, str]) -> dict[str, str]:
    print(f"\n  {DIM}Configure at least one AI provider to power your agents.{R}")
    print(f"  {DIM}Press Enter to skip a provider.{R}\n")
    providers = [
        ("ANTHROPIC_AUTH_TOKEN",  "Anthropic (Claude)",        "sk-ant-..."),
        ("OPENAI_API_KEY",        "OpenAI (GPT-4o, o1...)",    "sk-..."),
        ("GEMINI_API_KEY",        "Google Gemini",              "AIza..."),
        ("ZAI_API_KEY",           "GLM / Z.AI",                 "..."),
        ("MISTRAL_API_KEY",       "Mistral AI",                 "..."),
        ("DEEPSEEK_API_KEY",      "DeepSeek",                   "sk-..."),
        ("KIMI_API_KEY",          "Kimi (Moonshot)",            "sk-..."),
        ("QWEN_API_KEY",          "Qwen (Alibaba)",             "sk-..."),
    ]
    updates: dict[str, str] = {}
    for env_key, label, hint in providers:
        current = env.get(env_key, "")
        masked = f"{current[:8]}..." if len(current) > 8 else ("(set)" if current else "(not set)")
        prefix = f"{GRN}✓{R}" if current else f"{DIM}○{R}"
        val = input(
            f"  {prefix} {WHT}{label}{R} {DIM}[{masked}]{R}"
            f"{DIM} (Enter to keep){R}: "
        ).strip()
        if val:
            updates[env_key] = val
            env[env_key] = val
            ok(f"{label} configured")
        elif current:
            ok(f"{label} already configured")
    if updates:
        save_env(updates)
        ok("API keys saved to .env")
    return env

def configure_telegram(env: dict[str, str]) -> dict[str, str]:
    current = env.get("TELEGRAM_BOT_TOKENS", "")
    masked = f"{current[:12]}..." if len(current) > 12 else ("(set)" if current else "(not set)")
    print(f"\n  {DIM}Get a bot token from @BotFather on Telegram.{R}\n")
    val = input(
        f"  {WHT}Bot token(s){R} {DIM}[{masked}]{R}"
        f"{DIM} (Enter to keep){R}: "
    ).strip()
    if val:
        env["TELEGRAM_BOT_TOKENS"] = val
        save_env({"TELEGRAM_BOT_TOKENS": val})
        ok("Bot token saved")
    elif current:
        ok("Bot token already configured")
    else:
        warn("No Telegram bot token set")
    return env

def start_services(*, prod: bool = False) -> bool:
    info("Building and starting services...")
    print()
    r = dc("up", "-d", "--build", check=False, prod=prod)
    if r.returncode != 0:
        fail("docker compose up failed")
        return False
    ok("Containers started")
    return True

def wait_healthy(timeout: int = 90) -> bool:
    url = "http://localhost:8000/api/healthz"
    deadline = time.time() + timeout
    sys.stdout.write(f"  {BLU}→{R}  Waiting for backend")
    sys.stdout.flush()
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    print(f" {GRN}ready!{R}")
                    return True
        except Exception:
            pass
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(2)
    print(f" {RED}timeout{R}")
    fail(f"Backend didn't become healthy within {timeout}s")
    return False

def create_admin(env: dict[str, str], password: str | None = None) -> bool:
    print()
    if not password:
        print(f"  {DIM}Create the admin account for the web dashboard.{R}\n")
        username = ask("Admin username", default="admin")
        password = ask("Admin password", secret=True)
        if not password:
            warn("Empty password — skipping admin creation")
            return False
    else:
        username = "admin"

    script = (
        "import sys, os; sys.path.insert(0, '/app')\n"
        "from app.persistence.database import SessionLocal\n"
        "from app.persistence.models import User, UserRole\n"
        "import bcrypt\n"
        "u = os.environ['MB_USER']\n"
        "p = os.environ['MB_PASS']\n"
        "with SessionLocal() as db:\n"
        "    ex = db.query(User).filter(User.username == u).first()\n"
        "    if ex:\n"
        "        if not ex.password_hash:\n"
        "            ex.password_hash = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()\n"
        "            ex.role = UserRole.admin\n"
        "            db.commit()\n"
        "            print('UPDATED')\n"
        "        else:\n"
        "            print('EXISTS')\n"
        "    else:\n"
        "        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()\n"
        "        db.add(User(username=u, password_hash=h, role=UserRole.admin))\n"
        "        db.commit()\n"
        "        print('CREATED')\n"
    )
    r = dc_exec("backend", "python", "-c", script,
                env_extra={"MB_USER": username, "MB_PASS": password})
    output = (r.stdout + r.stderr).strip()
    if "CREATED" in output or "UPDATED" in output:
        ok(f"Admin user '{username}' ready")
        return True
    elif "EXISTS" in output:
        ok(f"Admin user '{username}' already exists")
        return True
    else:
        fail(f"Could not create admin user: {output}")
        return False

def verify_e2e(env: dict[str, str]) -> None:
    """Post-setup end-to-end verification."""
    print()
    print(f"{BOLD}  Post-Setup Verification{R}")
    hr()

    # 1. Backend health
    try:
        with urllib.request.urlopen("http://localhost:8000/api/healthz", timeout=5) as resp:
            if resp.status == 200:
                ok("Backend API healthy")
            else:
                fail(f"Backend returned {resp.status}")
    except Exception as exc:
        fail(f"Backend unreachable: {exc}")

    # 2. Telegram validation
    tokens = [t.strip() for t in env.get("TELEGRAM_BOT_TOKENS", "").split(",") if t.strip()]
    bot_usernames = []
    for token in tokens:
        valid, detail = validate_telegram_token(token)
        if valid:
            ok(f"Telegram bot active: {detail}")
            bot_usernames.append(detail)
        else:
            fail(f"Telegram bot error: {detail}")

    # 3. Check bindings exist (via API)
    try:
        with urllib.request.urlopen("http://localhost:8000/api/bindings", timeout=5) as resp:
            bindings = json.loads(resp.read())
            if isinstance(bindings, list) and len(bindings) > 0:
                ok(f"Bindings configured: {len(bindings)}")
            else:
                warn("No bindings found — messages won't be routed")
    except Exception:
        warn("Could not check bindings (API may require auth)")

    # 4. Check providers exist
    try:
        with urllib.request.urlopen("http://localhost:8000/api/providers", timeout=5) as resp:
            providers = json.loads(resp.read())
            active = [p for p in providers if p.get("active")]
            with_key = [p for p in active if (p.get("config") or {}).get("api_key")]
            if with_key:
                ok(f"Active providers with keys: {len(with_key)}")
            elif active:
                warn(f"Active providers: {len(active)} (none with API keys)")
            else:
                fail("No active providers")
    except Exception:
        warn("Could not check providers (API may require auth)")

    # Summary
    if bot_usernames:
        print()
        print(f"  {GRN}{BOLD}Ready!{R} Send a message to your bot:")
        for username in bot_usernames:
            print(f"  {CYN}https://t.me/{username.lstrip('@')}{R}")

def show_summary(env: dict[str, str]) -> None:
    print()
    print(f"{BOLD}{GRN}  Setup complete!{R}")
    print()
    hr()
    print(f"  {BOLD}Access URLs{R}")
    print(f"  {DIM}Admin dashboard{R}  {WHT}http://localhost:5173{R}")
    print(f"  {DIM}REST API{R}         {WHT}http://localhost:8000{R}")
    print(f"  {DIM}API docs{R}         {WHT}http://localhost:8000/docs{R}")
    print(f"  {DIM}Analytics{R}        {WHT}http://localhost:8000/api/analytics/costs/summary{R}")
    print(f"  {DIM}Security audit{R}   {WHT}http://localhost:8000/api/analytics/security/audit{R}")
    hr()
    print(f"  {BOLD}Commands{R}")
    print(f"  {CYN}prime status{R}        {DIM}service status{R}")
    print(f"  {CYN}prime doctor{R}        {DIM}full health check{R}")
    print(f"  {CYN}prime logs{R}          {DIM}follow logs{R}")
    print(f"  {CYN}prime gateway url{R}   {DIM}all endpoints{R}")
    print()

# ── Doctor ───────────────────────────────────────────────────────────────────

def doctor() -> None:
    banner()
    print(f"{BOLD}  System Health Check{R}")
    hr()
    all_ok = True

    # Docker daemon
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if r.returncode == 0:
        ok("Docker daemon running")
    else:
        fail("Docker daemon not running")
        all_ok = False

    # Containers
    r = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode == 0:
        try:
            services = [json.loads(line) for line in r.stdout.strip().splitlines() if line]
        except json.JSONDecodeError:
            services = []
        for svc in services:
            name  = svc.get("Service") or svc.get("Name", "?")
            state = svc.get("State", "?")
            label = f"{name} ({state})"
            if state == "running":
                ok(label)
            else:
                fail(label)
                all_ok = False
        if not services:
            warn("No containers — run 'prime start'")
            all_ok = False
    else:
        warn("Could not list containers")

    # Backend API
    try:
        with urllib.request.urlopen("http://localhost:8000/api/healthz", timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                db_ok = data.get("db") or data.get("database") or data.get("status") == "ok"
                ok("Backend API responding")
                if db_ok:
                    ok("Database connected")
                else:
                    warn("Database status unknown")
            else:
                fail(f"Backend returned {resp.status}")
                all_ok = False
    except Exception as exc:
        fail(f"Backend unreachable: {exc}")
        all_ok = False

    # .env
    if ENV_FILE.exists():
        ok(".env present")
    else:
        fail(".env missing — run 'prime onboard'")
        all_ok = False

    # Telegram + Provider validation
    env = load_env()
    validate_all_tokens(env)

    # Config YAML validation
    print()
    print(f"{BOLD}  Config Validation{R}")
    hr()
    for cfg_file in ["providers.yaml", "bots.yaml", "plugins.yaml"]:
        cfg_path = ROOT / "config" / cfg_file
        if cfg_path.exists():
            ok(f"{cfg_file} exists")
        else:
            warn(f"{cfg_file} missing")

    # Security audit (if backend running)
    try:
        with urllib.request.urlopen("http://localhost:8000/api/analytics/security/audit", timeout=5) as resp:
            audit = json.loads(resp.read())
            passed = audit.get("passed", 0)
            failed = audit.get("failed", 0)
            critical = audit.get("critical", 0)
            if critical > 0:
                fail(f"Security audit: {critical} critical, {failed} total issues")
                all_ok = False
            elif failed > 0:
                warn(f"Security audit: {failed} issues (no critical)")
            else:
                ok(f"Security audit: {passed} checks passed")
    except Exception:
        pass

    print()
    if all_ok:
        print(f"  {GRN}{BOLD}All systems healthy{R}")
    else:
        print(f"  {YLW}{BOLD}Issues found — see above{R}")
    print()

def repair() -> None:
    banner()
    print(f"{BOLD}  Repair Mode{R}")
    hr()
    ok_steps = 0

    r = dc_exec("backend", "bash", "-lc", "PYTHONPATH=/app alembic -c /app/alembic.ini upgrade head")
    if r.returncode == 0:
        ok("Migrations applied")
        ok_steps += 1
    else:
        fail("Migration failed")
        print((r.stdout + r.stderr).strip())

    r = dc_exec("backend", "python", "-c",
        "from app.services.config_sync import sync_config_to_db; sync_config_to_db(); print('ok')")
    if r.returncode == 0:
        ok("Config sync complete")
        ok_steps += 1
    else:
        fail("Config sync failed")
        print((r.stdout + r.stderr).strip())

    print()
    if ok_steps == 2:
        print(f"  {GRN}{BOLD}Repair complete{R}")
    else:
        print(f"  {YLW}{BOLD}Repair incomplete{R}")
    print()

def seed() -> None:
    banner()
    print(f"{BOLD}  Seeding data...{R}")
    hr()
    script = r"""
import sys, uuid
sys.path.insert(0, '/app')
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Provider, Binding, ProviderType, DMPolicy, Organization

with SessionLocal() as db:
    org = db.query(Organization).filter(Organization.slug == 'default').first()
    if not org:
        org = Organization(name='Prime', slug='default', active=True)
        db.add(org)
        db.commit()
        db.refresh(org)
        print('Org created: default')
    else:
        print('Org exists: default')

    p = db.query(Provider).filter(Provider.name == 'demo_anthropic').first()
    if not p:
        p = Provider(
            name='demo_anthropic',
            type=ProviderType.Anthropic,
            config={'api_key': '', 'default_model': 'claude-sonnet-4-5-20250929',
                    'models': {'claude-sonnet-4-5-20250929': {'max_tokens': 4096}}},
            active=True, org_id=org.id,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        print(f'Provider created: {p.name}')
    else:
        print(f'Provider exists: {p.name}')

    a = db.query(Agent).filter(Agent.name == 'demo_agent').first()
    if not a:
        a = Agent(
            name='demo_agent',
            description='Demo agent with web search and memory',
            default_provider_id=p.id,
            dm_policy=DMPolicy.open,
            memory_enabled=True, web_search_enabled=True,
            code_execution_enabled=True,
            system_prompt='You are a helpful assistant.',
            active=True, org_id=org.id,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        print(f'Agent created: {a.name}')
    else:
        print(f'Agent exists: {a.name}')

print('Seed complete.')
"""
    r = dc_exec("backend", "python", "-c", script)
    for line in (r.stdout + r.stderr).strip().splitlines():
        if line.strip():
            ok(line.strip()) if "created" in line.lower() else info(line.strip())
    print()

# ── Auto mode ────────────────────────────────────────────────────────────────

def auto_onboard(*, prod: bool = False, admin_pass: str | None = None) -> None:
    """Non-interactive full setup from environment variables."""
    banner()
    print(f"{BOLD}  Automated Onboarding{R}")
    hr()

    # Step 1: Prerequisites
    if not check_prereqs():
        fail("Prerequisites not met")
        sys.exit(1)

    # Step 2: Generate .env
    print()
    print(f"{BOLD}  Environment{R}")
    hr()
    if ENV_FILE.exists():
        env = load_env()
        ok(".env already exists")
    else:
        env = generate_env_from_example()
        save_env(env)
        ok(".env generated from template + env vars")

    env = setup_env(env)

    # Merge any env vars that are set in the shell
    shell_overrides = {}
    for key in ("TELEGRAM_BOT_TOKENS", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                "DEEPSEEK_API_KEY", "KIMI_API_KEY", "ZAI_API_KEY", "MISTRAL_API_KEY",
                "GEMINI_API_KEY", "QWEN_API_KEY", "DOMAIN", "APP_PUBLIC_URL",
                "DISCORD_BOT_CONFIGS"):
        val = os.getenv(key)
        if val and val != env.get(key):
            shell_overrides[key] = val
            env[key] = val
    if shell_overrides:
        save_env(shell_overrides)
        ok(f"Merged {len(shell_overrides)} env var(s) from shell")

    # Step 3: Validate keys
    validate_all_tokens(env)

    # Step 4: Start services
    print()
    print(f"{BOLD}  Starting Services{R}")
    hr()
    if not start_services(prod=prod):
        sys.exit(1)

    # Step 5: Health check
    print()
    print(f"{BOLD}  Health Check{R}")
    hr()
    healthy = wait_healthy(timeout=120)

    # Step 6: Admin user
    if healthy:
        admin_password = admin_pass or os.getenv("PRIME_ADMIN_PASSWORD", "")
        if admin_password:
            create_admin(env, password=admin_password)
        else:
            info("No PRIME_ADMIN_PASSWORD set — skipping admin creation")
            info("Set PRIME_ADMIN_PASSWORD env var or run: prime onboard (interactive)")

    # Step 7: Post-setup verification
    if healthy:
        verify_e2e(env)

    show_summary(env)

    if not healthy:
        sys.exit(1)

# ── Main ─────────────────────────────────────────────────────────────────────

def _interactive_onboard() -> None:
    banner()
    env = load_env()
    if ENV_FILE.exists() and env.get("SECRET_KEY") not in ("", "replace_me", None):
        print(f"  {DIM}Existing .env detected.{R}")
        if not confirm("Re-run full setup?", default=False):
            doctor()
            return

    TOTAL = 8

    step(1, TOTAL, "Prerequisites")
    if not check_prereqs():
        fail("Fix the issues above and re-run.")
        sys.exit(1)

    step(2, TOTAL, "Environment & Secrets")
    env = setup_env(env)

    step(3, TOTAL, "AI Providers")
    env = configure_providers(env)

    step(4, TOTAL, "Telegram Bot Token")
    env = configure_telegram(env)

    step(5, TOTAL, "Validate Keys")
    validate_all_tokens(env)

    step(6, TOTAL, "Starting Services")
    if not start_services(prod=False):
        sys.exit(1)

    step(7, TOTAL, "Health Check")
    healthy = wait_healthy(timeout=90)
    if not healthy:
        warn("Backend not ready — check logs")

    step(8, TOTAL, "Admin User & Verification")
    if healthy:
        create_admin(env)
        verify_e2e(env)
    else:
        warn("Skipping — backend not ready")

    show_summary(env)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.getenv("PRIME_CLI_PROG", "prime onboard"),
        description="Prime onboarding wizard / doctor / repair tool",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--doctor", action="store_true", help="Run full health + connectivity check")
    mode.add_argument("--repair", action="store_true", help="Apply migrations + config sync")
    mode.add_argument("--seed", action="store_true", help="Seed demo data")
    mode.add_argument("--validate", action="store_true", help="Validate keys only (no docker changes)")
    mode.add_argument("--auto", action="store_true", help="Non-interactive onboarding (env vars only)")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Production mode (uses docker-compose.prod.yml if present). "
        "When used alone, runs auto onboarding in prod mode.",
    )
    parser.add_argument("--admin-pass", default=None, help="Admin password for --auto/--prod mode")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.doctor:
        doctor()
        return
    if args.repair:
        repair()
        return
    if args.seed:
        seed()
        return
    if args.validate:
        banner()
        env = load_env()
        validate_all_tokens(env)
        return

    if args.auto or args.prod:
        auto_onboard(prod=bool(args.prod), admin_pass=args.admin_pass)
        return

    _interactive_onboard()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {YLW}Interrupted.{R}\n")
        sys.exit(0)
