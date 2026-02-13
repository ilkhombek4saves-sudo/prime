#!/usr/bin/env python3
"""
MultiBot Aggregator — Interactive Setup Wizard

Usage:
  python scripts/onboard.py            # full first-time setup
  python scripts/onboard.py --doctor   # health check only
  python scripts/onboard.py --seed     # seed demo data only
"""
from __future__ import annotations

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

# ── Python version guard ───────────────────────────────────────────────────────
if sys.version_info < (3, 10):
    print("ERROR: Python 3.10+ is required.")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

# ── ANSI colours ──────────────────────────────────────────────────────────────
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

# ── Output helpers ─────────────────────────────────────────────────────────────
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
    if secret:
        val = getpass(full)
    else:
        val = input(full)
    return val.strip() or default

def ask_choice(prompt: str, options: list[tuple[str, str]], default: str = "") -> str:
    """Show a numbered menu and return the chosen key."""
    print(f"\n  {WHT}{prompt}{R}")
    for i, (key, label) in enumerate(options, 1):
        mark = f"{GRN}▸{R}" if key == default else " "
        print(f"  {mark} {DIM}{i}.{R} {label}")
    while True:
        raw = input(f"\n  Choice {DIM}[1-{len(options)}]{R}: ").strip()
        if not raw and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        warn("Invalid choice, try again.")

def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    val = input(f"  {WHT}{prompt}{R} {DIM}[{hint}]{R}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")

# ── Banner ─────────────────────────────────────────────────────────────────────
def banner() -> None:
    print()
    print(f"{BOLD}{CYN} ███╗   ███╗██╗   ██╗██╗  ████████╗██╗██████╗  ██████╗ ████████╗{R}")
    print(f"{BOLD}{CYN} ████╗ ████║██║   ██║██║  ╚══██╔══╝██║██╔══██╗██╔═══██╗╚══██╔══╝{R}")
    print(f"{BOLD}{CYN} ██╔████╔██║██║   ██║██║     ██║   ██║██████╔╝██║   ██║   ██║   {R}")
    print(f"{BOLD}{CYN} ██║╚██╔╝██║██║   ██║██║     ██║   ██║██╔══██╗██║   ██║   ██║   {R}")
    print(f"{BOLD}{CYN} ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║██████╔╝╚██████╔╝   ██║   {R}")
    print(f"{BOLD}{CYN} ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝╚═════╝  ╚═════╝    ╚═╝   {R}")
    print()
    print(f" {DIM}MultiBot Aggregator  ·  AI-powered Telegram bot platform{R}")
    print()

# ── .env helpers ──────────────────────────────────────────────────────────────
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
    """Merge updates into the existing .env, appending new keys."""
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

# ── docker compose wrapper ────────────────────────────────────────────────────
def dc(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose"] + list(args)
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

# ── Step implementations ───────────────────────────────────────────────────────

def check_prereqs() -> bool:
    """Step 1: Verify Docker and docker compose are available."""
    all_ok = True

    # Docker
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if r.returncode == 0:
        ok("Docker is running")
    else:
        fail("Docker is not running — please start Docker Desktop or the Docker daemon")
        all_ok = False

    # docker compose (v2 plugin)
    r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if r.returncode == 0:
        ver = r.stdout.strip().split("version")[-1].strip()
        ok(f"Docker Compose {ver}")
    else:
        fail("docker compose not found — install Docker Desktop or the Compose plugin")
        all_ok = False

    return all_ok


def setup_env(env: dict[str, str]) -> dict[str, str]:
    """Step 2: Generate secrets and write core .env values."""
    changed = False

    # Auto-generate secrets if missing or placeholder
    for key, label in [("SECRET_KEY", "SECRET_KEY"), ("JWT_SECRET", "JWT_SECRET")]:
        if not env.get(key) or env[key] in ("replace_me", "replace_me_too", ""):
            env[key] = secrets.token_hex(32)
            ok(f"Generated {label}")
            changed = True
        else:
            ok(f"{label} already set")

    # Core settings
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
    """Step 3: Configure AI provider API keys."""
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

    any_configured = any(env.get(k) for k, _, _ in providers)
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
    elif not any_configured:
        warn("No AI providers configured — agents won't be able to respond")

    return env


def configure_telegram(env: dict[str, str]) -> dict[str, str]:
    """Step 4: Configure Telegram bot token(s)."""
    current = env.get("TELEGRAM_BOT_TOKENS", "")
    masked = f"{current[:12]}..." if len(current) > 12 else ("(set)" if current else "(not set)")

    print(f"\n  {DIM}Get a bot token from @BotFather on Telegram.{R}")
    print(f"  {DIM}Multiple tokens: separate with commas.{R}\n")

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
        warn("No Telegram bot token set — you can add it later in .env")

    return env


def start_services() -> bool:
    """Step 5: Start Docker services."""
    print()
    info("Building and starting services (this may take a minute)...")
    print()

    r = dc("up", "-d", "--build", check=False)
    if r.returncode != 0:
        fail("docker compose up failed — check output above")
        return False

    ok("Containers started")
    return True


def wait_healthy(timeout: int = 60) -> bool:
    """Step 6: Wait until backend /api/healthz responds 200."""
    url = "http://localhost:8000/api/healthz"
    deadline = time.time() + timeout

    print()
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


def create_admin(env: dict[str, str]) -> bool:
    """Step 7: Create an admin user inside the running backend container."""
    print()
    print(f"  {DIM}Create the admin account for the web dashboard.{R}\n")

    username = ask("Admin username", default="admin")
    password = ask("Admin password", secret=True)
    if not password:
        warn("Empty password — skipping admin creation")
        return False

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
        "        print('EXISTS')\n"
        "    else:\n"
        "        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()\n"
        "        db.add(User(username=u, password_hash=h, role=UserRole.admin))\n"
        "        db.commit()\n"
        "        print('CREATED')\n"
    )

    r = dc_exec("backend", "python", "-c", script,
                env_extra={"MB_USER": username, "MB_PASS": password})

    output = (r.stdout + r.stderr).strip()
    if "CREATED" in output:
        ok(f"Admin user '{username}' created")
        return True
    elif "EXISTS" in output:
        ok(f"Admin user '{username}' already exists")
        return True
    else:
        fail(f"Could not create admin user: {output}")
        return False


def show_summary(env: dict[str, str]) -> None:
    """Final step: show access URLs and next steps."""
    print()
    print(f"{BOLD}{GRN}  🎉  Setup complete!{R}")
    print()
    hr()
    print(f"  {BOLD}Access URLs{R}")
    print(f"  {DIM}Admin dashboard{R}  {WHT}http://localhost:5173{R}")
    print(f"  {DIM}REST API{R}         {WHT}http://localhost:8000{R}")
    print(f"  {DIM}API docs{R}         {WHT}http://localhost:8000/docs{R}")
    print(f"  {DIM}Metrics{R}          {WHT}http://localhost:8000/api/metrics{R}")
    hr()
    print(f"  {BOLD}Next steps{R}")
    print(f"  {DIM}1.{R} Open the admin dashboard and log in")
    print(f"  {DIM}2.{R} Create a bot (Bots → Add Bot) and link it to an agent")
    print(f"  {DIM}3.{R} Configure providers (Providers → Add Provider)")
    print(f"  {DIM}4.{R} Set up a Binding to route the bot to an agent")
    print()
    print(f"  {DIM}Useful commands:{R}")
    print(f"  {CYN}make logs{R}     {DIM}  follow live logs{R}")
    print(f"  {CYN}make status{R}   {DIM}  container status{R}")
    print(f"  {CYN}make doctor{R}   {DIM}  health check{R}")
    print(f"  {CYN}make shell{R}    {DIM}  backend bash shell{R}")
    print(f"  {CYN}make stop{R}     {DIM}  stop everything{R}")
    print()


# ── Doctor (health check) ──────────────────────────────────────────────────────
def doctor() -> None:
    banner()
    print(f"{BOLD}  System Health Check{R}")
    hr()

    all_ok = True

    # 1. Docker daemon
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if r.returncode == 0:
        ok("Docker daemon running")
    else:
        fail("Docker daemon not running")
        all_ok = False

    # 2. Containers running
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
            name   = svc.get("Service") or svc.get("Name", "?")
            state  = svc.get("State", "?")
            health = svc.get("Health", "")
            label  = f"{name}  ({state}{', ' + health if health else ''})"
            if state == "running":
                ok(label)
            else:
                fail(label)
                all_ok = False
        if not services:
            warn("No containers found — run 'make start' first")
            all_ok = False
    else:
        warn("Could not list containers")

    # 3. Backend API
    try:
        with urllib.request.urlopen("http://localhost:8000/api/healthz", timeout=5) as resp:
            if resp.status == 200:
                ok("Backend API responding")
            else:
                fail(f"Backend API returned {resp.status}")
                all_ok = False
    except Exception as exc:
        fail(f"Backend API not reachable: {exc}")
        all_ok = False

    # 4. Database connection (via healthz)
    try:
        with urllib.request.urlopen("http://localhost:8000/api/healthz", timeout=5) as resp:
            data = json.loads(resp.read())
            db_ok = data.get("db") or data.get("database")
            if db_ok:
                ok("Database connected")
            else:
                warn("Database status unknown from healthz")
    except Exception:
        pass

    # 5. .env exists
    if ENV_FILE.exists():
        ok(".env file present")
    else:
        fail(".env missing — run 'make onboard'")
        all_ok = False

    print()
    if all_ok:
        print(f"  {GRN}{BOLD}All systems healthy ✓{R}")
    else:
        print(f"  {YLW}{BOLD}Some issues found — see above{R}")
    print()


# ── Seed demo data ─────────────────────────────────────────────────────────────
def seed() -> None:
    banner()
    print(f"{BOLD}  Seeding demo data...{R}")
    hr()

    script = r"""
import sys, uuid
sys.path.insert(0, '/app')
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Provider, Binding, ProviderType, DMPolicy
import bcrypt

with SessionLocal() as db:
    # Provider
    p = db.query(Provider).filter(Provider.name == 'demo_anthropic').first()
    if not p:
        p = Provider(
            name='demo_anthropic',
            type=ProviderType.Anthropic,
            config={
                'api_key': '',
                'default_model': 'claude-sonnet-4-5-20250929',
                'models': {'claude-sonnet-4-5-20250929': {'max_tokens': 4096}},
            },
            active=True,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        print(f'Provider created: {p.name}')
    else:
        print(f'Provider exists: {p.name}')

    # Agent
    a = db.query(Agent).filter(Agent.name == 'demo_agent').first()
    if not a:
        a = Agent(
            name='demo_agent',
            description='Demo agent with web search and memory',
            default_provider_id=p.id,
            dm_policy=DMPolicy.open,
            memory_enabled=True,
            web_search_enabled=True,
            code_execution_enabled=True,
            system_prompt='You are a helpful assistant.',
            active=True,
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


# ── Main flow ──────────────────────────────────────────────────────────────────
def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "--doctor":
        doctor()
        return

    if mode == "--seed":
        seed()
        return

    banner()

    # Check if already set up
    env = load_env()
    if ENV_FILE.exists() and env.get("SECRET_KEY") not in ("", "replace_me", None):
        print(f"  {DIM}Existing .env detected.{R}")
        if not confirm("Re-run full setup?", default=False):
            # Just show doctor
            print()
            doctor()
            return

    TOTAL = 7

    # Step 1 — prerequisites
    step(1, TOTAL, "Prerequisites")
    if not check_prereqs():
        print()
        fail("Prerequisites not met — fix the issues above and re-run.")
        sys.exit(1)

    # Step 2 — env / secrets
    step(2, TOTAL, "Environment & Secrets")
    env = setup_env(env)

    # Step 3 — AI providers
    step(3, TOTAL, "AI Providers")
    env = configure_providers(env)

    # Step 4 — Telegram
    step(4, TOTAL, "Telegram Bot Token")
    env = configure_telegram(env)

    # Step 5 — start services
    step(5, TOTAL, "Starting Services")
    if not start_services():
        sys.exit(1)

    # Step 6 — wait for health
    step(6, TOTAL, "Health Check")
    healthy = wait_healthy(timeout=90)
    if not healthy:
        warn("Backend not ready yet — you can check with 'make logs'")

    # Step 7 — admin user
    step(7, TOTAL, "Admin User")
    if healthy:
        create_admin(env)
    else:
        warn("Skipping admin creation — backend not ready")
        info("Run again after services start: python scripts/onboard.py")

    # Done
    show_summary(env)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {YLW}Interrupted.{R}\n")
        sys.exit(0)
