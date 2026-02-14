#!/usr/bin/env python3
"""
Prime CLI — Command-line interface for the Prime AI Agent
OpenClaw-compatible command surface.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Auto-load settings
from prime.config.settings import settings

R = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[91m"; GRN = "\033[92m"; YLW = "\033[93m"; BLU = "\033[94m"; CYN = "\033[96m"
MAG = "\033[95m"

BACKEND_URL = os.getenv("PRIME_BACKEND_URL", "http://localhost:8000")
BACKEND_TOKEN = os.getenv("PRIME_BACKEND_TOKEN", "")


def _http(method: str, path: str, **kwargs):
    """Make authenticated HTTP request to backend."""
    import httpx
    headers = kwargs.pop("headers", {})
    if BACKEND_TOKEN:
        headers["Authorization"] = f"Bearer {BACKEND_TOKEN}"
    url = f"{BACKEND_URL}{path}"
    try:
        resp = httpx.request(method, url, headers=headers, timeout=15, **kwargs)
        return resp
    except Exception as exc:
        return None


def _run_script(script_name: str, args: list) -> None:
    """Run a script from the scripts/ directory and exit with its return code."""
    import subprocess
    script = Path(__file__).parent.parent / "scripts" / script_name
    if not script.exists():
        print(f"\n  {RED}✗{R} Script not found: {script}\n")
        sys.exit(1)
    result = subprocess.run([sys.executable, str(script)] + list(args))
    sys.exit(result.returncode)


# ── Status ─────────────────────────────────────────────────────────────────────

def cmd_status():
    from prime.core.agent import get_system_info
    info = get_system_info()
    print(f"\n{BOLD}{CYN}{'=' * 48}")
    print(f"  PRIME STATUS")
    print(f"{'=' * 48}{R}\n")
    print(f"  {GRN}✓{R} Hostname:    {info['hostname']}")
    print(f"  {GRN}✓{R} OS:          {info['os']}")
    print(f"  {GRN}✓{R} Environment: {info['environment']}")
    print(f"  {GRN}✓{R} Workspace:   {info['workspace']}")
    print(f"  {GRN}✓{R} User:        {info['user']}")

    print(f"\n{BOLD}API Keys:{R}")
    for name, key in [
        ("DeepSeek", settings.DEEPSEEK_API_KEY),
        ("Kimi", settings.KIMI_API_KEY),
        ("Gemini", settings.GEMINI_API_KEY),
        ("OpenAI", settings.OPENAI_API_KEY),
        ("Anthropic", settings.ANTHROPIC_API_KEY),
    ]:
        if key:
            print(f"  {GRN}✓{R} {name}: {key[:12]}...")
        else:
            print(f"  {YLW}!{R} {name}: not set")

    provider = settings.best_provider()
    print(f"\n{BOLD}Active Provider:{R} {GRN}{provider or 'NONE'}{R}\n")

    try:
        from prime.core.memory import get_db
        stats = get_db().stats()
        print(f"{BOLD}Database:{R}")
        for k, v in stats.items():
            print(f"  • {k}: {v}")
        print()
    except Exception as e:
        print(f"  {YLW}!{R} DB: {e}\n")

    # Backend health check
    resp = _http("GET", "/healthz")
    if resp and resp.status_code == 200:
        data = resp.json()
        status_str = GRN + "ok" + R if data.get("status") == "ok" else YLW + "degraded" + R
        print(f"{BOLD}Backend:{R} {status_str} (DB: {'✓' if data.get('db') else '✗'})\n")
    else:
        print(f"{BOLD}Backend:{R} {YLW}not reachable{R} ({BACKEND_URL})\n")


# ── Doctor ─────────────────────────────────────────────────────────────────────

def cmd_doctor():
    """Deep diagnostic: checks all subsystems."""
    print(f"\n{BOLD}{CYN}Prime Doctor{R} — running diagnostics...\n")

    # Try backend doctor endpoint first
    resp = _http("GET", "/api/doctor")
    if resp and resp.status_code == 200:
        data = resp.json()
        checks = data.get("checks", [])
        print(f"  {DIM}Source: backend ({BACKEND_URL}){R}\n")
        for c in checks:
            icon = GRN + "✓" + R if c["ok"] else RED + "✗" + R
            print(f"  {icon} {BOLD}{c['label']:<22}{R} {c['detail']}")
            if not c["ok"] and c.get("fix"):
                print(f"    {DIM}→ Fix: {c['fix']}{R}")
        passed = data.get("passed", 0)
        total = data.get("total", len(checks))
        color = GRN if data.get("healthy") else YLW
        print(f"\n  {color}{BOLD}{passed}/{total} checks passed{R}\n")
        return

    # Fallback: local checks
    print(f"  {DIM}Backend not reachable — running local checks{R}\n")
    _local_doctor_checks()


def _local_doctor_checks():
    import shutil
    import platform

    checks = []

    def chk(label, ok, detail="", fix=""):
        icon = GRN + "✓" + R if ok else RED + "✗" + R
        print(f"  {icon} {BOLD}{label:<22}{R} {detail}")
        if not ok and fix:
            print(f"    {DIM}→ Fix: {fix}{R}")
        checks.append(ok)

    py = sys.version_info
    chk("python_version", py >= (3, 10), f"Python {py.major}.{py.minor}.{py.micro}", "Upgrade to Python 3.10+")

    provider = settings.best_provider()
    chk("provider_keys", bool(provider), f"Active: {provider or 'none'}", "Set at least one API key in .env")

    ws_path = Path(settings.WORKSPACE)
    chk("workspace", ws_path.exists(), str(ws_path), f"mkdir -p {ws_path}")

    docker_ok = shutil.which("docker") is not None
    chk("docker", docker_ok, "found" if docker_ok else "not in PATH", "Install Docker")

    ts_ok = shutil.which("tailscale") is not None
    chk("tailscale", ts_ok, "found" if ts_ok else "not installed (optional)", "curl -fsSL https://tailscale.com/install.sh | sh")

    node_ok = shutil.which("node") is not None
    chk("nodejs", node_ok, "found" if node_ok else "not installed (optional)", "Install Node.js 18+")

    # Check backend reachability
    import httpx
    try:
        r = httpx.get(f"{BACKEND_URL}/healthz", timeout=3)
        chk("backend", r.status_code == 200, f"HTTP {r.status_code}", "docker compose up -d backend")
    except Exception:
        chk("backend", False, "not reachable", f"docker compose up -d backend (URL: {BACKEND_URL})")

    passed = sum(1 for c in checks if c)
    total = len(checks)
    color = GRN if passed == total else YLW
    print(f"\n  {color}{BOLD}{passed}/{total} checks passed{R}\n")


# ── Security ───────────────────────────────────────────────────────────────────

def cmd_security():
    """Run security audit."""
    print(f"\n{BOLD}{MAG}Prime Security Audit{R}\n")

    resp = _http("GET", "/api/security/audit")
    if resp and resp.status_code == 200:
        data = resp.json()
        print(f"  {DIM}Source: backend{R}\n")
        findings = data.get("findings", [])
        if not findings:
            print(f"  {GRN}✓ All security checks passed ({data.get('passed', 0)} checks){R}\n")
            return
        for f in findings:
            sev = f["severity"]
            color = RED if sev == "critical" else YLW if sev == "warning" else BLU
            icon = "✗" if sev == "critical" else "!" if sev == "warning" else "i"
            print(f"  {color}{icon} [{sev.upper()}]{R} {BOLD}{f['code']}{R}")
            print(f"    {f['message']}")
            print(f"    {DIM}Fix: {f['fix']}{R}\n")
        print(f"  {BOLD}Passed: {data.get('passed', 0)} | Failed: {data.get('failed', 0)} | Critical: {data.get('critical', 0)}{R}\n")
        return

    # Fallback: local security check
    print(f"  {DIM}Backend not reachable — running local checks{R}\n")
    _local_security_checks()


def _local_security_checks():
    checks_passed = 0
    checks_total = 0

    def audit(ok, code, message, fix):
        nonlocal checks_passed, checks_total
        checks_total += 1
        if ok:
            checks_passed += 1
            print(f"  {GRN}✓{R} {code}")
        else:
            sev_color = RED
            print(f"  {sev_color}✗ {BOLD}{code}{R}: {message}")
            print(f"    {DIM}Fix: {fix}{R}")

    secret = os.getenv("SECRET_KEY", "change-me")
    audit(secret not in ("change-me", "secret", "") and len(secret) >= 16,
          "SECRET_KEY", "Default or too short", "Set SECRET_KEY to 32+ random chars in .env")

    jwt = os.getenv("JWT_SECRET", "change-me-too")
    audit(jwt not in ("change-me-too", "secret", ""),
          "JWT_SECRET", "Default value", "Set JWT_SECRET to 32+ random chars in .env")

    db_url = os.getenv("DATABASE_URL", "sqlite://")
    audit("sqlite" not in db_url,
          "DATABASE_URL", "Using SQLite (not prod-ready)", "Switch to PostgreSQL")

    print(f"\n  {BOLD}Passed: {checks_passed}/{checks_total}{R}\n")


# ── Logs ───────────────────────────────────────────────────────────────────────

def cmd_logs(args: list[str]):
    """Tail colorized logs from backend or local log file."""
    n = 50  # default lines
    follow = "-f" in args or "--follow" in args
    for a in args:
        if a.isdigit():
            n = int(a)

    # Try docker logs
    import shutil
    if shutil.which("docker"):
        container = _find_docker_container()
        if container:
            import subprocess
            tail_args = ["docker", "logs", "--tail", str(n)]
            if follow:
                tail_args.append("-f")
            tail_args.append(container)
            print(f"\n{DIM}Streaming logs from container: {container}{R}\n")
            try:
                subprocess.run(tail_args)
                return
            except KeyboardInterrupt:
                return

    # Try local log file
    log_file = Path(os.getenv("PRIME_LOG_FILE", "/tmp/prime.log"))
    if log_file.exists():
        print(f"\n{DIM}Tailing {log_file}{R}\n")
        _tail_file(log_file, n, follow)
        return

    print(f"\n{YLW}No log source found.{R}")
    print(f"  • Start with Docker: docker compose up -d")
    print(f"  • Set PRIME_LOG_FILE env var to point to your log file\n")


def _find_docker_container() -> str | None:
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=prime", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5,
        )
        names = [n.strip() for n in result.stdout.splitlines() if n.strip()]
        # Prefer 'prime-backend' or 'prime_backend'
        for n in names:
            if "backend" in n:
                return n
        return names[0] if names else None
    except Exception:
        return None


def _tail_file(path: Path, n: int, follow: bool):
    import time
    lines = path.read_text(errors="replace").splitlines()
    for line in lines[-n:]:
        _print_log_line(line)
    if follow:
        try:
            with path.open() as f:
                f.seek(0, 2)  # seek to end
                while True:
                    line = f.readline()
                    if line:
                        _print_log_line(line.rstrip())
                    else:
                        time.sleep(0.1)
        except KeyboardInterrupt:
            pass


def _print_log_line(line: str):
    """Colorize log output by severity."""
    lower = line.lower()
    if " error" in lower or "critical" in lower or "exception" in lower:
        print(RED + line + R)
    elif " warning" in lower or " warn" in lower:
        print(YLW + line + R)
    elif " info" in lower:
        print(GRN + line + R)
    elif " debug" in lower:
        print(DIM + line + R)
    else:
        print(line)


# ── Models ─────────────────────────────────────────────────────────────────────

def cmd_models():
    """List available AI providers and models with credential scan."""
    print(f"\n{BOLD}{CYN}Prime Models — Provider Scan{R}\n")

    providers = [
        ("DeepSeek", "DEEPSEEK_API_KEY", "deepseek-chat, deepseek-reasoner", "deepseek"),
        ("Kimi (Moonshot)", "KIMI_API_KEY", "moonshot-v1-8k, moonshot-v1-32k", "kimi"),
        ("Google Gemini", "GEMINI_API_KEY", "gemini-2.0-flash, gemini-1.5-pro", "gemini"),
        ("OpenAI", "OPENAI_API_KEY", "gpt-4o, gpt-4o-mini, gpt-4-turbo", "openai"),
        ("Anthropic", "ANTHROPIC_API_KEY", "claude-opus-4-6, claude-sonnet-4-5", "anthropic"),
        ("Ollama", "OLLAMA_HOST", "llama3.2, mistral, qwen2.5 (local)", "ollama"),
    ]

    active = settings.best_provider()
    for name, env, models, key in providers:
        val = os.getenv(env, "")
        if val:
            star = f" {GRN}★ ACTIVE{R}" if key == active else ""
            print(f"  {GRN}✓{R} {BOLD}{name}{R}{star}")
            print(f"    {DIM}Key: {val[:12]}...{R}")
            print(f"    {DIM}Models: {models}{R}")
        else:
            print(f"  {DIM}○ {name} — not configured (set {env}){R}")
        print()

    # Try to list models from backend
    resp = _http("GET", "/api/providers")
    if resp and resp.status_code == 200:
        data = resp.json()
        print(f"  {DIM}Backend providers: {len(data)} configured{R}\n")


# ── Update ─────────────────────────────────────────────────────────────────────

def cmd_update():
    """Self-update Prime from git / pip."""
    import subprocess
    print(f"\n{BOLD}{CYN}Prime Update{R}\n")

    # Detect install path
    prime_dir = Path(__file__).parent.parent
    git_dir = prime_dir / ".git"

    if git_dir.exists():
        print(f"  Pulling latest from git...")
        try:
            result = subprocess.run(
                ["git", "-C", str(prime_dir), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                print(f"  {GRN}✓{R} {result.stdout.strip()}")
            else:
                print(f"  {RED}✗{R} git pull failed:\n{result.stderr.strip()}")
                return
        except Exception as exc:
            print(f"  {RED}✗{R} Update failed: {exc}")
            return
    else:
        print(f"  {YLW}!{R} Not a git repository. Use pip to update:")
        print(f"    pip install --upgrade prime-agent")
        return

    # Re-install requirements
    req = prime_dir / "requirements.txt"
    if req.exists():
        print(f"  Installing requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req), "-q"])
        print(f"  {GRN}✓{R} Requirements updated")

    print(f"\n  {GRN}✓{R} Prime updated successfully. Restart to apply changes.\n")


# ── Nodes ──────────────────────────────────────────────────────────────────────

def cmd_nodes():
    """Show connected WebSocket nodes."""
    print(f"\n{BOLD}{CYN}Connected Nodes{R}\n")

    resp = _http("GET", "/api/sessions")
    if resp and resp.status_code == 200:
        sessions = resp.json()
        if not sessions:
            print(f"  {DIM}No active sessions{R}\n")
            return
        for s in sessions[:20]:
            status_color = GRN if s.get("status") == "active" else DIM
            print(f"  {status_color}●{R} {BOLD}{s.get('session_key', '?')}{R}")
            print(f"    {DIM}Agent: {s.get('agent_id', 'default')} | Status: {s.get('status', '?')}{R}")
    else:
        print(f"  {YLW}Backend not reachable. Connect to {BACKEND_URL}{R}\n")
        print(f"  {DIM}Set PRIME_BACKEND_URL and PRIME_BACKEND_TOKEN env vars{R}\n")


# ── DNS ────────────────────────────────────────────────────────────────────────

def cmd_dns():
    """Show Tailscale DNS / wide-area discovery info."""
    import shutil
    print(f"\n{BOLD}{CYN}Tailscale DNS / Wide-Area Discovery{R}\n")

    if not shutil.which("tailscale"):
        print(f"  {YLW}!{R} Tailscale not installed.")
        print(f"  Install: curl -fsSL https://tailscale.com/install.sh | sh\n")
        return

    import subprocess
    try:
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"  {YLW}!{R} Tailscale not connected. Run: tailscale up\n")
            return
        import json
        data = json.loads(result.stdout)
        self_node = data.get("Self", {})
        peers = data.get("Peer", {})

        hostname = self_node.get("HostName", "unknown")
        dns_name = self_node.get("DNSName", "")
        tailnet_ip = self_node.get("TailscaleIPs", [""])[0]
        print(f"  {GRN}✓{R} {BOLD}This node:{R} {hostname}")
        print(f"    DNS:  {dns_name or '(not set)'}")
        print(f"    IP:   {tailnet_ip}\n")

        if peers:
            print(f"  {BOLD}Tailnet peers ({len(peers)}):{R}")
            for _, peer in list(peers.items())[:10]:
                online = GRN + "●" + R if peer.get("Online") else DIM + "○" + R
                peer_ips = peer.get("TailscaleIPs", [""])[0]
                print(f"    {online} {peer.get('HostName', '?'):20s} {peer_ips}")
        print()

        # Check funnel status via backend
        resp = _http("GET", "/api/tailscale/status")
        if resp and resp.status_code == 200:
            ts_data = resp.json()
            funnel_url = ts_data.get("funnel_url")
            if funnel_url:
                print(f"  {GRN}✓{R} Funnel URL: {BOLD}{funnel_url}{R}")
                print(f"  Webhook endpoint: {funnel_url}hooks/{{path}}\n")
    except Exception as exc:
        print(f"  {RED}✗{R} Error: {exc}\n")


# ── Auth ───────────────────────────────────────────────────────────────────────

def cmd_auth(args: list[str]):
    """Manage authentication — login, logout, status."""
    sub = args[0] if args else "status"

    if sub == "status":
        if BACKEND_TOKEN:
            print(f"\n  {GRN}✓{R} Logged in (token: {BACKEND_TOKEN[:12]}...)")
        else:
            print(f"\n  {YLW}!{R} Not logged in. Set PRIME_BACKEND_TOKEN or run: prime auth login\n")
        return

    if sub == "login":
        username = input("Username: ").strip()
        import getpass
        password = getpass.getpass("Password: ")
        import httpx
        try:
            resp = httpx.post(
                f"{BACKEND_URL}/api/auth/token",
                data={"username": username, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token", "")
                print(f"\n  {GRN}✓{R} Login successful!")
                print(f"  Add to your shell profile:")
                print(f"    export PRIME_BACKEND_TOKEN={token}\n")
            else:
                print(f"\n  {RED}✗{R} Login failed: {resp.json().get('detail', 'unknown error')}\n")
        except Exception as exc:
            print(f"\n  {RED}✗{R} Connection failed: {exc}\n")
        return

    if sub == "whoami":
        _run_script("auth.py", ["whoami"])
        return

    print(f"\n  Usage: prime auth [status|login|whoami]\n")


# ── TUI ────────────────────────────────────────────────────────────────────────

def cmd_tui():
    """Launch Terminal UI dashboard."""
    try:
        _run_tui()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"\n{RED}TUI error: {exc}{R}")
        print(f"Falling back to interactive mode...\n")
        from prime.core.agent import InteractiveSession
        InteractiveSession().run()


def _run_tui():
    """Simple curses-based TUI for Prime."""
    import curses
    import threading
    import time
    import uuid

    from prime.core.agent import Agent

    state = {
        "messages": [],
        "input": "",
        "provider": settings.best_provider() or "none",
        "status": "Ready",
        "agent": None,
        "session_id": f"tui-{uuid.uuid4().hex[:8]}",
    }

    def run(stdscr):
        curses.curs_set(1)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)

        state["agent"] = Agent(
            session_id=state["session_id"],
            channel="tui",
        )

        def draw():
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # Header
            header = f" PRIME TUI  |  Provider: {state['provider']}  |  Session: {state['session_id']} "
            stdscr.addstr(0, 0, header[:w-1], curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(0, len(header) if len(header) < w else w-1, " " * (w - len(header) - 1))

            # Status bar (line 1)
            stdscr.addstr(1, 0, f" {state['status']}"[:w-1], curses.color_pair(2))

            # Messages area
            msg_area_h = h - 5
            messages = state["messages"]
            start = max(0, len(messages) - msg_area_h)
            for i, (role, text) in enumerate(messages[start:start + msg_area_h]):
                y = i + 2
                if y >= h - 3:
                    break
                if role == "user":
                    prefix = ">> "
                    attr = curses.color_pair(3)
                else:
                    prefix = "   "
                    attr = curses.A_NORMAL
                line = f"{prefix}{text}"[:w-1]
                try:
                    stdscr.addstr(y, 0, line, attr)
                except curses.error:
                    pass

            # Separator
            sep_y = h - 3
            stdscr.addstr(sep_y, 0, "─" * (w-1), curses.color_pair(5))

            # Input line
            input_prompt = f">> {state['input']}"
            try:
                stdscr.addstr(h - 2, 0, input_prompt[:w-1])
                stdscr.move(h - 2, min(len(input_prompt), w - 2))
            except curses.error:
                pass

            # Help line
            help_line = " [Enter] Send  [Ctrl+C] Quit  [/reset] Clear  [/status] Status "
            try:
                stdscr.addstr(h - 1, 0, help_line[:w-1], curses.A_DIM)
            except curses.error:
                pass

            stdscr.refresh()

        draw()
        stdscr.nodelay(False)
        stdscr.keypad(True)

        while True:
            draw()
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == 3:  # Ctrl+C
                break
            elif ch in (curses.KEY_ENTER, 10, 13):
                query = state["input"].strip()
                state["input"] = ""
                if not query:
                    continue

                if query == "/quit":
                    break
                elif query == "/reset":
                    state["messages"] = []
                    state["agent"].reset()
                    state["status"] = "Conversation reset"
                    continue
                elif query == "/status":
                    state["messages"].append(("assistant", f"Provider: {state['provider']} | Session: {state['session_id']}"))
                    continue

                state["messages"].append(("user", query))
                state["status"] = "Thinking..."
                draw()

                def do_chat(q):
                    try:
                        resp = state["agent"].chat(q)
                        # Wrap long lines
                        h, w = stdscr.getmaxyx()
                        for chunk in _wrap_text(resp, w - 6):
                            state["messages"].append(("assistant", chunk))
                        state["status"] = "Ready"
                    except Exception as exc:
                        state["messages"].append(("assistant", f"Error: {exc}"))
                        state["status"] = "Error"
                    draw()
                    stdscr.refresh()

                t = threading.Thread(target=do_chat, args=(query,), daemon=True)
                t.start()
                t.join()

            elif ch == curses.KEY_BACKSPACE or ch == 127:
                state["input"] = state["input"][:-1]
            elif 32 <= ch <= 126:
                state["input"] += chr(ch)

    curses.wrapper(run)


def _wrap_text(text: str, width: int) -> list[str]:
    """Wrap text to fit terminal width."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        while len(paragraph) > width:
            lines.append(paragraph[:width])
            paragraph = paragraph[width:]
        lines.append(paragraph)
    return lines


# ── Pairing ────────────────────────────────────────────────────────────────────

def cmd_pairing(args: list[str]):
    """Manage device pairing (approve/reject DM access)."""
    sub = args[0] if args else "list"

    if sub == "list":
        resp = _http("GET", "/api/pairing/pending")
        if resp and resp.status_code == 200:
            items = resp.json()
            if not items:
                print(f"\n  {DIM}No pending pairing requests{R}\n")
                return
            print(f"\n{BOLD}Pending Pairing Requests:{R}\n")
            for item in items:
                print(f"  {YLW}?{R} {BOLD}{item.get('device_name', '?')}{R}")
                print(f"    ID: {item.get('id', '?')}")
                print(f"    Channel: {item.get('channel', '?')}")
                print(f"    Requested: {item.get('created_at', '?')}\n")
        else:
            print(f"\n  {YLW}Backend not reachable{R}\n")
        return

    if sub == "approve" and len(args) >= 2:
        device_id = args[1]
        resp = _http("POST", f"/api/pairing/{device_id}/approve")
        if resp and resp.status_code == 200:
            print(f"\n  {GRN}✓{R} Device {device_id} approved\n")
        else:
            print(f"\n  {RED}✗{R} Failed to approve device\n")
        return

    if sub == "reject" and len(args) >= 2:
        device_id = args[1]
        resp = _http("POST", f"/api/pairing/{device_id}/reject")
        if resp and resp.status_code == 200:
            print(f"\n  {GRN}✓{R} Device {device_id} rejected\n")
        else:
            print(f"\n  {RED}✗{R} Failed to reject device\n")
        return

    print(f"\n  Usage: prime pairing [list|approve <id>|reject <id>]\n")


# ── Cron ───────────────────────────────────────────────────────────────────────

def cmd_cron(args: list[str]):
    """Manage scheduled jobs."""
    sub = args[0] if args else "list"

    if sub == "list":
        resp = _http("GET", "/api/cron")
        if resp and resp.status_code == 200:
            jobs = resp.json()
            if not jobs:
                print(f"\n  {DIM}No cron jobs configured{R}\n")
                return
            print(f"\n{BOLD}Cron Jobs:{R}\n")
            for j in jobs:
                active = GRN + "●" + R if j.get("active") else DIM + "○" + R
                print(f"  {active} {BOLD}{j.get('name', '?'):<20}{R} {j.get('schedule', '?')}")
                print(f"    {DIM}Next: {j.get('next_run', 'unknown')}{R}")
        else:
            print(f"\n  {YLW}Backend not reachable{R}\n")
        return

    print(f"\n  Use the API or dashboard to manage cron jobs\n")
    print(f"  POST {BACKEND_URL}/api/cron  {{name, schedule, message}}\n")


# ── Webhooks ───────────────────────────────────────────────────────────────────

def cmd_webhooks(args: list[str]):
    """Manage webhook bindings."""
    sub = args[0] if args else "list"

    if sub == "list":
        resp = _http("GET", "/api/webhooks")
        if resp and resp.status_code == 200:
            hooks = resp.json()
            if not hooks:
                print(f"\n  {DIM}No webhooks configured{R}\n")
                return
            print(f"\n{BOLD}Webhooks:{R}\n")
            for h in hooks:
                active = GRN + "●" + R if h.get("active") else DIM + "○" + R
                print(f"  {active} {BOLD}{h.get('name', '?'):<20}{R} /{h.get('path', '?')}")
                print(f"    {DIM}URL: {BACKEND_URL}/hooks{h.get('path', '?')}{R}")
        else:
            print(f"\n  {YLW}Backend not reachable{R}\n")
        return

    print(f"\n  Usage: prime webhooks [list]\n")
    print(f"  POST {BACKEND_URL}/api/webhooks  {{name, path, message_template}}\n")


# ── Skills ─────────────────────────────────────────────────────────────────────

def cmd_skills():
    """List available skills."""
    # Try backend first
    resp = _http("GET", "/api/skills")
    if resp and resp.status_code == 200:
        skills = resp.json()
        print(f"\n{BOLD}{CYN}Available Skills ({len(skills)}):{R}\n")
        for s in skills:
            icon = "⚙" if s.get("type") == "bundled" else "📦"
            print(f"  {icon} {BOLD}{s.get('name', '?'):<20}{R} {DIM}{s.get('description', '')}{R}")
        print()
        return

    # Fallback: local lite registry
    from prime.skills.registry import get_registry
    skills = get_registry().list_skills()
    print(f"\n{BOLD}{CYN}Available Skills (local):{R}\n")
    for s in skills:
        icon = "⚙" if s["type"] == "builtin" else "📦"
        print(f"  {icon} {s['name']:20s} {DIM}{s['description']}{R}")
    print()


# ── Memory ─────────────────────────────────────────────────────────────────────

def cmd_memory(args: list[str]):
    """Show memory stats and entries."""
    sub = args[0] if args else "list"

    if sub == "list":
        # Try backend
        resp = _http("GET", "/api/memory")
        if resp and resp.status_code == 200:
            items = resp.json()
            print(f"\n{BOLD}{CYN}Memories ({len(items)}):{R}\n")
            for m in items[:20]:
                print(f"  {BLU}•{R} {m.get('content', '')[:80]}")
                if m.get("tags"):
                    print(f"    {DIM}Tags: {', '.join(m['tags'])}{R}")
            print()
            return

        # Fallback: local
        from prime.core.memory import get_db
        db = get_db()
        stats = db.stats()
        print(f"\n{BOLD}{CYN}Memory ({stats['memories']} entries):{R}\n")
        mems = db.list_memories()
        if mems:
            for m in mems[:20]:
                print(f"  {BLU}•{R} {BOLD}{m['key']}{R}: {m['content'][:80]}")
        else:
            print(f"  {DIM}No memories yet.{R}")
        print()
        return

    if sub == "search" and len(args) >= 2:
        query = " ".join(args[1:])
        resp = _http("GET", "/api/memory", params={"q": query})
        if resp and resp.status_code == 200:
            items = resp.json()
            print(f"\n{BOLD}Search results for '{query}':{R}\n")
            for m in items[:10]:
                print(f"  {BLU}•{R} {m.get('content', '')[:80]}")
            print()
        return

    print(f"\n  Usage: prime memory [list|search <query>]\n")


# ── Tailscale ──────────────────────────────────────────────────────────────────

def cmd_tailscale(args: list[str]):
    """Manage Tailscale VPN/funnel."""
    sub = args[0] if args else "status"

    if sub == "status":
        resp = _http("GET", "/api/tailscale/status")
        if resp and resp.status_code == 200:
            data = resp.json()
            print(f"\n{BOLD}{CYN}Tailscale Status:{R}\n")
            print(f"  Connected:  {GRN if data.get('connected') else YLW}{data.get('connected', False)}{R}")
            print(f"  Hostname:   {data.get('hostname', 'unknown')}")
            print(f"  Tailnet IP: {data.get('tailnet_ip', 'none')}")
            print(f"  Funnel URL: {data.get('funnel_url', 'none')}\n")
        else:
            cmd_dns()
        return

    if sub == "connect" and len(args) >= 2:
        auth_key = args[1].replace("--auth-key=", "").replace("--authkey=", "")
        resp = _http("POST", "/api/tailscale/connect", json={"auth_key": auth_key})
        if resp and resp.status_code == 200:
            print(f"\n  {GRN}✓{R} Connected to Tailscale\n")
        else:
            print(f"\n  {RED}✗{R} Failed to connect\n")
        return

    if sub == "funnel":
        port = int(args[1]) if len(args) >= 2 else 8000
        resp = _http("POST", "/api/tailscale/funnel", json={"port": port})
        if resp and resp.status_code == 200:
            data = resp.json()
            print(f"\n  {GRN}✓{R} Funnel started: {data.get('url', '')}\n")
        else:
            print(f"\n  {RED}✗{R} Failed to start funnel\n")
        return

    print(f"\n  Usage: prime tailscale [status|connect <auth-key>|funnel [port]]\n")


# ── Telegram ───────────────────────────────────────────────────────────────────

def cmd_telegram():
    """Start Telegram bot in long-polling mode."""
    from prime.integrations.telegram import run_polling
    run_polling()


# ── Gateway ────────────────────────────────────────────────────────────────────

def cmd_gateway(args: list):
    """Start the Gateway server or query it (status/health/call/url)."""
    if args and args[0] in ("status", "health", "call", "url"):
        if args[0] == "url":
            _cmd_gateway_url()
            return
        _run_script("gateway_cli.py", args)
        return
    # No subcommand — start the gateway server
    try:
        from prime.gateway.server import main as gateway_main
        gateway_main()
    except ImportError as e:
        print(f"  {RED}✗{R} Gateway requires FastAPI: pip install fastapi uvicorn")
        print(f"    Error: {e}")


def _cmd_gateway_url():
    """Print all service URLs."""
    api_url = os.getenv("PRIME_API_URL", "http://localhost:8000")
    dash_url = os.getenv("PRIME_DASHBOARD_URL", f"http://localhost:{settings.GATEWAY_PORT}")
    print(f"\n{BOLD}{CYN}Prime Service URLs{R}\n")
    print(f"  {BOLD}REST API{R}        {BLU}{api_url}{R}")
    print(f"  {BOLD}API Docs{R}        {BLU}{api_url}/docs{R}")
    print(f"  {BOLD}Health{R}          {BLU}{api_url}/api/healthz{R}")
    print(f"  {BOLD}Dashboard{R}       {BLU}{dash_url}{R}")
    print(f"  {BOLD}WebSocket{R}       {BLU}ws://localhost:8000/ws{R}")
    print()


# ── Onboard ────────────────────────────────────────────────────────────────────

def cmd_onboard(args: list):
    """Run the interactive setup wizard (or auto/doctor/repair/seed/validate)."""
    _run_script("onboard.py", args)


# ── Start / Stop ───────────────────────────────────────────────────────────────

def cmd_start(args: list):
    """Start all Docker services."""
    import subprocess
    root = Path(__file__).parent.parent
    prod = "--prod" in args
    compose_file = "docker-compose.prod.yml" if prod else "docker-compose.yml"
    print(f"\n{BOLD}{CYN}Starting Prime...{R}\n")
    result = subprocess.run(
        ["docker", "compose", "-f", str(root / compose_file), "up", "-d"],
        cwd=str(root),
    )
    if result.returncode == 0:
        print(f"\n  {GRN}✓{R} Services started")
        print(f"  Backend:   {BLU}http://localhost:8000{R}")
        print(f"  Dashboard: {BLU}http://localhost:5173{R}")
        print(f"\n  {DIM}Logs: prime logs -f{R}\n")
    sys.exit(result.returncode)


def cmd_stop(args: list):
    """Stop all Docker services."""
    import subprocess
    root = Path(__file__).parent.parent
    down_args = ["docker", "compose", "down"]
    if "--volumes" in args or "-v" in args:
        down_args.append("-v")
    print(f"\n{BOLD}{CYN}Stopping Prime...{R}\n")
    result = subprocess.run(down_args, cwd=str(root))
    if result.returncode == 0:
        print(f"\n  {GRN}✓{R} Services stopped\n")
    sys.exit(result.returncode)


# ── Channels ───────────────────────────────────────────────────────────────────

def cmd_channels(args: list):
    """Manage channels (Telegram bots, connectors)."""
    _run_script("channels.py", args if args else ["list"])


# ── Dashboard ──────────────────────────────────────────────────────────────────

def cmd_dashboard(args: list):
    """Show or open the web dashboard."""
    dash_url = os.getenv("PRIME_DASHBOARD_URL", f"http://localhost:{settings.GATEWAY_PORT}")
    print(f"\n  {BOLD}Dashboard:{R} {BLU}{dash_url}{R}\n")
    if "--open" in args or not args:
        import webbrowser
        webbrowser.open(dash_url)
        print(f"  {GRN}✓{R} Opened in browser\n")


# ── Shell ──────────────────────────────────────────────────────────────────────

def cmd_shell():
    """Launch an interactive Python shell with prime context pre-loaded."""
    import code
    ns: dict = {"settings": settings, "os": os, "Path": Path}
    try:
        from prime.core.agent import Agent
        from prime.core.memory import get_db
        ns.update({"Agent": Agent, "get_db": get_db})
    except Exception:
        pass
    banner_msg = (
        f"\n{BOLD}{CYN}Prime Shell{R}\n"
        f"{DIM}Available: Agent, settings, get_db, os, Path{R}\n"
        f"{DIM}Type Ctrl+D to exit.{R}\n"
    )
    code.interact(banner=banner_msg, local=ns)


# ── Help ────────────────────────────────────────────────────────────────────────

def cmd_help():
    print(f"""
{BOLD}{CYN}Prime — Production AI Agent{R}
{DIM}OpenClaw-compatible multi-agent platform{R}

{BOLD}Usage:{R}
  prime [OPTIONS] [COMMAND|QUERY]

{BOLD}Setup & Lifecycle:{R}
  onboard [--auto|--prod|--doctor|--repair|--seed|--validate]
                   Interactive setup wizard (first-time setup)
  start [--prod]   Start all Docker services
  stop [-v]        Stop all Docker services
  update           Self-update from git or pip

{BOLD}Core Commands:{R}
  status           Show system status, API keys, DB stats
  doctor           Deep health diagnostics (all subsystems)
  security         Security audit — misconfigurations, weak secrets
  logs [-f] [N]    Tail colorized logs (follow with -f, last N lines)
  models           List AI providers and configured models

{BOLD}Gateway Commands:{R}
  gateway [status|health|call <method>|url]
                   Start Gateway server or query it
  telegram         Start Telegram bot (long-polling)
  channels [list|doctor|live|connect|verify]
                   Manage Telegram/Discord channels
  nodes            Show connected WebSocket nodes
  dns              Show Tailscale DNS / wide-area discovery
  dashboard [--open]  Show or open the web dashboard

{BOLD}Management Commands:{R}
  auth [login|status|whoami]  Manage API authentication
  pairing [list|approve|reject]  Device pairing approval flow
  cron [list]      Manage scheduled jobs
  webhooks [list]  Manage webhook bindings
  skills           List available skills
  memory [list|search]  Manage agent memory
  tailscale [status|connect|funnel]  Tailscale VPN/funnel

{BOLD}Interactive:{R}
  shell            Interactive Python shell with prime context
  tui              Launch Terminal UI dashboard
  (no args)        Start interactive chat session

{BOLD}Options:{R}
  --provider NAME  Force provider (deepseek, kimi, gemini, openai, anthropic)
  --model MODEL    Use specific model
  --telegram, -t   Send response to Telegram chat

{BOLD}Examples:{R}
  prime onboard                     # first-time interactive setup
  prime onboard --auto              # non-interactive setup (reads env vars)
  prime onboard --doctor            # health check
  prime start                       # docker compose up -d
  prime stop                        # docker compose down
  prime status
  prime doctor
  prime logs -f
  prime gateway status
  prime gateway url
  prime channels list
  prime dashboard --open
  prime auth login
  prime auth whoami
  prime shell
  prime "What files are in this directory?"

{BOLD}Environment:{R}
  PRIME_BACKEND_URL    Backend URL (default: http://localhost:8000)
  PRIME_BACKEND_TOKEN  Bearer token for backend API

{BOLD}Providers:{R}
  deepseek    DeepSeek API (fast, cheap, default)
  kimi        Moonshot AI (Chinese/English)
  gemini      Google Gemini
  openai      OpenAI GPT
  anthropic   Anthropic Claude

{BOLD}Architecture:{R}
  • CLI → direct agent execution (SQLite, no Docker)
  • Backend → REST API + WebSocket + PostgreSQL (port 8000)
  • Dashboard → http://localhost:{settings.GATEWAY_PORT}/
  • Channels: Telegram, Discord, Slack, WhatsApp, WebChat
""")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        from prime.core.agent import InteractiveSession
        InteractiveSession().run()
        return

    # Parse options
    provider = None
    model = None
    use_telegram = False
    query_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1]; i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] in ("--telegram", "-t"):
            use_telegram = True; i += 1
        else:
            query_parts.append(args[i]); i += 1

    if not query_parts:
        from prime.core.agent import InteractiveSession
        InteractiveSession(provider=provider, model=model).run()
        return

    cmd = query_parts[0].lower()
    sub_args = query_parts[1:]

    # Command dispatch
    if cmd == "status":
        cmd_status()
    elif cmd == "doctor":
        cmd_doctor()
    elif cmd == "security":
        cmd_security()
    elif cmd == "logs":
        cmd_logs(sub_args)
    elif cmd == "models":
        cmd_models()
    elif cmd == "update":
        cmd_update()
    elif cmd == "nodes":
        cmd_nodes()
    elif cmd == "dns":
        cmd_dns()
    elif cmd == "tui":
        cmd_tui()
    elif cmd == "auth":
        cmd_auth(sub_args)
    elif cmd == "pairing":
        cmd_pairing(sub_args)
    elif cmd == "cron":
        cmd_cron(sub_args)
    elif cmd == "webhooks":
        cmd_webhooks(sub_args)
    elif cmd == "skills":
        cmd_skills()
    elif cmd == "memory":
        cmd_memory(sub_args)
    elif cmd == "tailscale":
        cmd_tailscale(sub_args)
    elif cmd == "telegram":
        cmd_telegram()
    elif cmd == "gateway":
        cmd_gateway(sub_args)
    elif cmd == "onboard":
        cmd_onboard(sub_args)
    elif cmd == "start":
        cmd_start(sub_args)
    elif cmd == "stop":
        cmd_stop(sub_args)
    elif cmd == "channels":
        cmd_channels(sub_args)
    elif cmd == "dashboard":
        cmd_dashboard(sub_args)
    elif cmd == "shell":
        cmd_shell()
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    else:
        # Agent query
        import uuid
        query = " ".join(query_parts)
        from prime.core.agent import Agent

        session_id = f"cli-{uuid.uuid4().hex[:8]}"
        agent = Agent(session_id=session_id, provider=provider, model=model, channel="cli")
        response = agent.chat(query)
        print(f"\n{response}\n")

        if use_telegram:
            from prime.integrations.telegram import notify
            notify(f"📡 Query: `{query}`\n\n{response}")
            print(f"{GRN}✓{R} Response sent to Telegram\n")


if __name__ == "__main__":
    main()
