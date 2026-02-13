#!/usr/bin/env python3
"""
Prime Lite — Personal AI Agent (OpenClaw-like)
Single-binary mode with SQLite, built-in UI, simple CLI
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

# Setup paths
PRIME_HOME = Path(os.environ.get("PRIME_HOME", Path.home() / ".prime"))
CONFIG_DIR = Path.home() / ".config" / "prime"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = CONFIG_DIR / ".env"
LOG_FILE = CONFIG_DIR / "prime.log"
PID_FILE = CONFIG_DIR / "prime.pid"
DB_FILE = CONFIG_DIR / "prime.db"

# Colors
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"
WHT = "\033[97m"


def log(msg: str) -> None:
    print(f"  {BLU}→{R} {msg}")


def ok(msg: str) -> None:
    print(f"  {GRN}✓{R} {msg}")


def warn(msg: str) -> None:
    print(f"  {YLW}!{R} {msg}")


def error(msg: str) -> None:
    print(f"  {RED}✗{R} {msg}", file=sys.stderr)


def banner():
    print()
    print(f"{BOLD}{CYN} ██████╗ ██████╗ ██╗███╗   ███╗███████╗{R}")
    print(f"{BOLD}{CYN} ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝{R}")
    print(f"{BOLD}{CYN} ██████╔╝██████╔╝██║██╔████╔██║█████╗  {R}")
    print(f"{BOLD}{CYN} ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  {R}")
    print(f"{BOLD}{CYN} ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗{R}")
    print(f"{BOLD}{CYN} ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝{R}")
    print(f"{DIM}    Lite Mode — Personal AI Agent{R}")
    print()


def load_env():
    """Load .env file into environment"""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if k and k not in os.environ:
                    os.environ[k] = v


def init_database():
    """Initialize SQLite database"""
    log("Initializing database...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            channel TEXT,
            status TEXT DEFAULT 'active',
            context TEXT
        )
    """)
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    ok(f"Database ready: {DB_FILE}")


def check_ollama() -> bool:
    """Check if Ollama is running"""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except:
        return False


def get_ollama_models() -> list[str]:
    """Get list of Ollama models"""
    import urllib.request
    import json
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except:
        return []


def cmd_init(args):
    """Initialize Prime Lite"""
    banner()
    
    # Create directories
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Config directory: {CONFIG_DIR}")
    
    # Create config
    if not CONFIG_FILE.exists():
        config = {
            "version": 1,
            "mode": "lite",
            "database": {"type": "sqlite", "path": str(DB_FILE)},
            "providers": {
                "ollama": {
                    "type": "Ollama",
                    "api_base": "http://localhost:11434/v1",
                    "default_model": "llama3.2",
                    "models": {}
                }
            },
            "server": {"host": "127.0.0.1", "port": 18789}
        }
        
        # Detect available models
        if check_ollama():
            models = get_ollama_models()
            if models:
                config["providers"]["ollama"]["default_model"] = models[0]
                for m in models:
                    config["providers"]["ollama"]["models"][m] = {"max_tokens": 4096}
                ok(f"Found Ollama models: {', '.join(models)}")
        
        import yaml
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        ok(f"Created config: {CONFIG_FILE}")
    else:
        warn(f"Config exists: {CONFIG_FILE}")
    
    # Create .env
    if not ENV_FILE.exists():
        import secrets
        env_content = f"""# Prime Lite Environment
SECRET_KEY={secrets.token_hex(32)}
JWT_SECRET={secrets.token_hex(32)}
APP_ENV=production
TELEGRAM_BOT_TOKEN=
"""
        ENV_FILE.write_text(env_content)
        ENV_FILE.chmod(0o600)
        ok(f"Created .env: {ENV_FILE}")
    
    # Init database
    init_database()
    
    print()
    ok("Prime Lite initialized!")
    print()
    print(f"{BOLD}Next steps:{R}")
    print(f"  1. Add Telegram token: nano {ENV_FILE}")
    print(f"  2. Start server:       prime serve")
    print(f"  3. Open dashboard:     prime dashboard")
    print()


def cmd_serve(args):
    """Start Prime Lite server"""
    load_env()
    
    if not CONFIG_FILE.exists():
        error("Prime not initialized. Run: prime init")
        sys.exit(1)
    
    # Check Ollama
    if not check_ollama():
        warn("Ollama not running. Start with: ollama serve")
        print()
    
    import yaml
    config = yaml.safe_load(CONFIG_FILE.read_text())
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 18789)
    
    log(f"Starting Prime Lite on http://{host}:{port}")
    
    # Set environment for backend
    env = os.environ.copy()
    env["PRIME_LITE"] = "1"
    env["PRIME_CONFIG"] = str(CONFIG_FILE)
    env["DATABASE_URL"] = f"sqlite:///{DB_FILE}"
    env["APP_PORT"] = str(port)
    
    try:
        # Try to run from repo
        backend_path = Path(__file__).parent.parent / "backend"
        if (backend_path / "app" / "main.py").exists():
            os.chdir(backend_path)
            subprocess.run([
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", host, "--port", port,
                "--reload" if args.dev else ""
            ], env=env)
        else:
            # Fallback: create minimal FastAPI app
            start_minimal_server(host, port)
    except KeyboardInterrupt:
        print()
        log("Shutting down...")


def start_minimal_server(host: str, port: int):
    """Start minimal FastAPI server for lite mode"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn
    except ImportError:
        error("FastAPI not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)
    
    app = FastAPI(title="Prime Lite")
    
    @app.get("/api/healthz")
    def health():
        return {"status": "ok", "mode": "lite", "ollama": check_ollama()}
    
    @app.get("/api/config")
    def get_config():
        import yaml
        return yaml.safe_load(CONFIG_FILE.read_text())
    
    @app.get("/api/models")
    def get_models():
        return {"models": get_ollama_models()}
    
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)
    
    uvicorn.run(app, host=host, port=port)


def cmd_status(args):
    """Check Prime status"""
    banner()
    
    # Check config
    if CONFIG_FILE.exists():
        ok(f"Config: {CONFIG_FILE}")
    else:
        error(f"Config not found: {CONFIG_FILE}")
        print(f"Run: prime init")
        return
    
    # Check database
    if DB_FILE.exists():
        ok(f"Database: {DB_FILE}")
    else:
        warn(f"Database not initialized")
    
    # Check Ollama
    if check_ollama():
        models = get_ollama_models()
        ok(f"Ollama running ({len(models)} models)")
        for m in models[:5]:
            print(f"       - {m}")
    else:
        error("Ollama not running")
        print("       Start with: ollama serve")
    
    # Check server
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:18789/api/healthz", timeout=1)
        ok("Server running on http://127.0.0.1:18789")
    except:
        warn("Server not running")
        print("       Start with: prime serve")


def cmd_doctor(args):
    """Run diagnostics"""
    banner()
    log("Running diagnostics...")
    print()
    
    checks = []
    
    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 10):
        checks.append(("Python 3.10+", True, f"{py_version}"))
    else:
        checks.append(("Python 3.10+", False, f"{py_version}"))
    
    # Config
    checks.append(("Config file", CONFIG_FILE.exists(), str(CONFIG_FILE)))
    
    # Database
    checks.append(("Database", DB_FILE.exists(), str(DB_FILE)))
    
    # Ollama
    checks.append(("Ollama running", check_ollama(), "http://localhost:11434"))
    
    # Models
    models = get_ollama_models()
    checks.append(("Ollama models", len(models) > 0, f"{len(models)} found"))
    
    # Server
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:18789/api/healthz", timeout=1)
        checks.append(("Server", True, "http://127.0.0.1:18789"))
    except:
        checks.append(("Server", False, "not running"))
    
    # Telegram token
    load_env()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    checks.append(("Telegram token", bool(tg_token), "set" if tg_token else "not set"))
    
    # Print results
    for name, ok_status, detail in checks:
        status = f"{GRN}✓{R}" if ok_status else f"{RED}✗{R}"
        print(f"  {status} {name:20} {DIM}{detail}{R}")
    
    print()
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    
    if passed == total:
        ok(f"All checks passed ({passed}/{total})")
    else:
        warn(f"Some checks failed ({passed}/{total})")


def cmd_dashboard(args):
    """Open dashboard"""
    url = "http://127.0.0.1:18789"
    
    if args.open:
        webbrowser.open(url)
    else:
        print(f"Dashboard: {url}")
        print(f"Open with: prime dashboard --open")


def cmd_logs(args):
    """View logs"""
    if LOG_FILE.exists():
        subprocess.run(["tail", "-f", str(LOG_FILE)])
    else:
        warn("No log file found")


def cmd_stop(args):
    """Stop Prime server"""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 15)  # SIGTERM
            ok(f"Stopped process {pid}")
            PID_FILE.unlink()
        except ProcessLookupError:
            warn("Process not found")
            PID_FILE.unlink()
    else:
        warn("No PID file found. Is server running?")


def cmd_agent(args):
    """Send message to agent with tool support (like OpenClaw)"""
    load_env()
    
    if not args.message:
        error("No message provided. Use: prime agent 'hello'")
        return
    
    # Check Ollama
    if not check_ollama():
        error("Ollama not running")
        return
    
    import urllib.request
    import json
    import os
    from pathlib import Path
    
    model = args.model or "llama3.2"
    workspace_path = os.environ.get("PRIME_WORKSPACE", ".")
    
    # Tool definitions (subset that works well with local models)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create or overwrite a file in the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List all files and directories in the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Subdirectory (default: root)"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run a shell command in the workspace directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web using DuckDuckGo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
    
    def execute_tool(name, arguments):
        """Execute a tool call"""
        try:
            if name == "write_file":
                p = Path(workspace_path) / arguments["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(arguments["content"], encoding="utf-8")
                return f"OK: written {arguments['path']}"
            elif name == "read_file":
                p = Path(workspace_path) / arguments["path"]
                if not p.exists():
                    return f"Error: file not found: {arguments['path']}"
                return p.read_text(encoding="utf-8")[:4000]
            elif name == "list_files":
                p = Path(workspace_path) / arguments.get("path", ".")
                if not p.exists():
                    return f"Error: directory not found"
                lines = []
                for item in sorted(p.rglob("*")):
                    rel = item.relative_to(workspace_path)
                    lines.append(("[dir]  " if item.is_dir() else "[file] ") + str(rel))
                return "\n".join(lines[:50]) or "(empty)"
            elif name == "run_command":
                import subprocess
                r = subprocess.run(
                    arguments["command"],
                    shell=True, capture_output=True, text=True,
                    cwd=workspace_path, timeout=60
                )
                out = (r.stdout + r.stderr).strip()
                return out[:2000] or "(no output)"
            elif name == "search_web":
                try:
                    from duckduckgo_search import DDGS
                    with DDGS() as ddgs:
                        results = list(ddgs.text(arguments["query"], max_results=5))
                    if not results:
                        return "No results found."
                    lines = []
                    for r in results:
                        lines.append(f"- {r.get('title', '')}: {r.get('body', '')[:100]}")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Search error: {e}"
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Tool error: {e}"
    
    def chat_with_tools(messages, max_turns=5):
        """Chat with tool calling loop"""
        for turn in range(max_turns):
            req_data = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False
            }
            
            req = urllib.request.Request(
                "http://localhost:11434/v1/chat/completions",
                data=json.dumps(req_data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                message = data["choices"][0]["message"]
                
                # Check if tool calls requested
                tool_calls = message.get("tool_calls")
                if tool_calls:
                    messages.append(message)
                    for tc in tool_calls:
                        name = tc["function"]["name"]
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except:
                            args = {}
                        
                        log(f"Tool: {name}({json.dumps(args)})")
                        result = execute_tool(name, args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result
                        })
                else:
                    # No tool calls - return final response
                    return message.get("content", "")
        
        return "Max turns reached"
    
    log(f"Sending to {model} (with tools)...")
    print()
    
    messages = [
        {"role": "system", "content": "You are Prime, an AI assistant with access to tools. Use tools when needed to help the user."},
        {"role": "user", "content": args.message}
    ]
    
    try:
        response = chat_with_tools(messages)
        print(response)
        print()
    except Exception as e:
        error(f"Request failed: {e}")


# Simple dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Prime Lite</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            padding: 2rem;
            text-align: center;
        }
        header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        header p { opacity: 0.9; }
        main { flex: 1; max-width: 1200px; margin: 0 auto; padding: 2rem; width: 100%; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid #334155;
        }
        .card h3 { color: #60a5fa; margin-bottom: 1rem; }
        .status { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; }
        .status.ok { background: #22c55e; }
        .status.warn { background: #eab308; }
        .status.error { background: #ef4444; }
        button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.2s;
        }
        button:hover { background: #2563eb; }
        .chat {
            background: #0f172a;
            border-radius: 8px;
            padding: 1rem;
            min-height: 200px;
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #334155;
        }
        .input-group {
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        input[type="text"] {
            flex: 1;
            background: #1e293b;
            border: 1px solid #334155;
            color: white;
            padding: 0.75rem;
            border-radius: 8px;
            font-size: 1rem;
        }
        pre {
            background: #0f172a;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.875rem;
        }
        footer {
            text-align: center;
            padding: 2rem;
            color: #64748b;
            border-top: 1px solid #334155;
        }
    </style>
</head>
<body>
    <header>
        <h1>🦞 Prime Lite</h1>
        <p>Personal AI Agent — Local & Private</p>
    </header>
    <main>
        <div class="grid">
            <div class="card">
                <h3>Status</h3>
                <div id="status-container">
                    <div class="status">
                        <span class="status-dot" id="ollama-dot"></span>
                        <span>Ollama</span>
                        <span id="ollama-status">Checking...</span>
                    </div>
                    <div class="status">
                        <span class="status-dot" id="server-dot"></span>
                        <span>Server</span>
                        <span id="server-status">Running</span>
                    </div>
                </div>
            </div>
            <div class="card">
                <h3>Quick Actions</h3>
                <button onclick="checkStatus()">Refresh Status</button>
                <button onclick="location.reload()">Reload</button>
            </div>
            <div class="card" style="grid-column: 1 / -1;">
                <h3>Chat (Local LLM)</h3>
                <div class="chat" id="chat"></div>
                <div class="input-group">
                    <input type="text" id="message" placeholder="Type a message..." 
                           onkeypress="if(event.key==='Enter')sendMessage()">
                    <button onclick="sendMessage()">Send</button>
                </div>
            </div>
            <div class="card">
                <h3>Config</h3>
                <pre id="config">Loading...</pre>
            </div>
            <div class="card">
                <h3>Models</h3>
                <pre id="models">Loading...</pre>
            </div>
        </div>
    </main>
    <footer>
        <p>Prime Lite — OpenClaw-inspired Personal AI</p>
    </footer>
    <script>
        async function checkStatus() {
            try {
                const resp = await fetch('/api/healthz');
                const data = await resp.json();
                
                document.getElementById('ollama-dot').className = 'status-dot ' + 
                    (data.ollama ? 'ok' : 'error');
                document.getElementById('ollama-status').textContent = 
                    data.ollama ? 'Connected' : 'Not running';
            } catch (e) {
                document.getElementById('ollama-dot').className = 'status-dot error';
                document.getElementById('ollama-status').textContent = 'Error';
            }
        }
        
        async function loadConfig() {
            try {
                const resp = await fetch('/api/config');
                const data = await resp.json();
                document.getElementById('config').textContent = JSON.stringify(data, null, 2);
            } catch (e) {
                document.getElementById('config').textContent = 'Error loading config';
            }
        }
        
        async function loadModels() {
            try {
                const resp = await fetch('/api/models');
                const data = await resp.json();
                document.getElementById('models').textContent = data.models.join('\\n');
            } catch (e) {
                document.getElementById('models').textContent = 'Error loading models';
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('message');
            const chat = document.getElementById('chat');
            const msg = input.value.trim();
            if (!msg) return;
            
            chat.innerHTML += `<div><strong>You:</strong> ${msg}</div>`;
            input.value = '';
            
            try {
                const resp = await fetch('http://localhost:11434/v1/chat/completions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        model: 'llama3.2',
                        messages: [{role: 'user', content: msg}],
                        stream: false
                    })
                });
                const data = await resp.json();
                const reply = data.choices[0].message.content;
                chat.innerHTML += `<div><strong>AI:</strong> ${reply}</div>`;
            } catch (e) {
                chat.innerHTML += `<div style="color:#ef4444"><strong>Error:</strong> ${e.message}</div>`;
            }
            chat.scrollTop = chat.scrollHeight;
        }
        
        checkStatus();
        loadConfig();
        loadModels();
    </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        prog="prime",
        description="Prime Lite — Personal AI Agent"
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    init_parser = subparsers.add_parser("init", help="Initialize Prime Lite")
    
    # serve
    serve_parser = subparsers.add_parser("serve", help="Start server")
    serve_parser.add_argument("--dev", action="store_true", help="Development mode")
    
    # status
    subparsers.add_parser("status", help="Check status")
    
    # doctor
    subparsers.add_parser("doctor", help="Run diagnostics")
    
    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Open dashboard")
    dash_parser.add_argument("--open", action="store_true", help="Open in browser")
    
    # logs
    subparsers.add_parser("logs", help="View logs")
    
    # stop
    subparsers.add_parser("stop", help="Stop server")
    
    # agent
    agent_parser = subparsers.add_parser("agent", help="Send message to agent")
    agent_parser.add_argument("message", help="Message to send")
    agent_parser.add_argument("--model", help="Model to use")
    
    # service
    service_parser = subparsers.add_parser("service", help="Manage systemd/launchd service")
    service_parser.add_argument("action", choices=["install", "uninstall", "start", "stop", "restart", "status", "logs"], 
                                help="Service action")
    
    # secrets
    secrets_parser = subparsers.add_parser("secrets", help="Manage secure secrets")
    secrets_parser.add_argument("action", choices=["set", "get", "delete", "list", "migrate"],
                               help="Secrets action")
    secrets_parser.add_argument("--service", help="Service name (for set/get/delete)")
    secrets_parser.add_argument("--value", help="Secret value (for set)")
    
    # update
    update_parser = subparsers.add_parser("update", help="Update Prime Lite")
    update_parser.add_argument("--apply", "-a", action="store_true", help="Apply available update")
    update_parser.add_argument("--force", "-f", action="store_true", help="Force reinstall")
    update_parser.add_argument("--check", "-c", action="store_true", help="Check for updates only")
    
    args = parser.parse_args()
    
    if not args.command:
        banner()
        parser.print_help()
        print()
        print(f"{BOLD}Quick start:{R}")
        print("  prime init              # Initialize")
        print("  prime serve             # Start server")
        print("  prime doctor            # Check health")
        print("  prime service install   # Install systemd/launchd daemon")
        print("  prime secrets migrate   # Encrypt .env secrets")
        print("  prime update --check    # Check for updates")
        sys.exit(0)
    
    def cmd_service(args):
        """Delegate to service manager"""
        import sys
        sys.argv = ["prime-service", args.action]
        import importlib.util
        service_path = Path(__file__).parent / "service.py"
        spec = importlib.util.spec_from_file_location("service", service_path)
        service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(service)
        service.main()
    
    def cmd_secrets(args):
        """Delegate to secrets manager"""
        import sys
        sys.argv = ["prime-secrets", args.action]
        if args.service:
            sys.argv.extend(["--service", args.service])
        if args.value:
            sys.argv.extend(["--value", args.value])
        import importlib.util
        secrets_path = Path(__file__).parent / "secrets.py"
        spec = importlib.util.spec_from_file_location("secrets", secrets_path)
        secrets = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(secrets)
        secrets.main()
    
    def cmd_update(args):
        """Delegate to updater"""
        import sys
        sys.argv = ["prime-update"]
        if args.apply:
            sys.argv.append("--apply")
        if args.force:
            sys.argv.append("--force")
        if args.check:
            sys.argv.append("--check")
        import importlib.util
        update_path = Path(__file__).parent / "update.py"
        spec = importlib.util.spec_from_file_location("update", update_path)
        update = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(update)
        update.main()
    
    commands = {
        "init": cmd_init,
        "serve": cmd_serve,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "dashboard": cmd_dashboard,
        "logs": cmd_logs,
        "stop": cmd_stop,
        "agent": cmd_agent,
        "service": cmd_service,
        "secrets": cmd_secrets,
        "update": cmd_update,
    }
    
    if args.command in commands:
        commands[args.command](args)
    else:
        error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
