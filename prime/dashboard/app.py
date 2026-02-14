"""
Prime Dashboard — Web UI for monitoring and control
Served at /dashboard by the Gateway
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from prime.config.settings import settings
from prime.core.agent import get_system_info
from prime.integrations.web import WEBCHAT_HTML


STATIC_DIR = Path(__file__).parent / "static"


def mount_dashboard(app) -> None:
    """Mount dashboard routes onto a FastAPI app."""
    if not HAS_FASTAPI:
        return

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        return HTMLResponse(DASHBOARD_HTML)

    @app.get("/chat", response_class=HTMLResponse)
    async def webchat(request: Request):
        return HTMLResponse(WEBCHAT_HTML)

    @app.get("/api/stats")
    async def stats():
        info = get_system_info()
        try:
            from prime.core.memory import get_db
            db_stats = get_db().stats()
        except Exception:
            db_stats = {}
        return {
            "system": info,
            "provider": settings.best_provider(),
            "providers": settings.available_providers(),
            "db": db_stats,
            "uptime": _get_uptime(),
            "timestamp": datetime.now().isoformat(),
        }


_start_time = datetime.now()


def _get_uptime() -> str:
    delta = datetime.now() - _start_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


# ─── Dashboard HTML ───────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prime Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0d1117; color: #e6edf3; min-height: 100vh; }
nav { background: #161b22; border-bottom: 1px solid #30363d; padding: 0 24px;
      display: flex; align-items: center; gap: 24px; height: 56px; }
.logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; color: #58a6ff; }
.logo-icon { width: 28px; height: 28px; background: linear-gradient(135deg,#58a6ff,#a371f7);
             border-radius: 7px; display: flex; align-items: center; justify-content: center; font-size: 13px; }
nav a { color: #7d8590; text-decoration: none; font-size: 14px; padding: 6px 12px;
        border-radius: 6px; transition: all 0.2s; }
nav a:hover { color: #e6edf3; background: #21262d; }
nav a.active { color: #e6edf3; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.status-badge { background: #1c2128; border: 1px solid #30363d; border-radius: 20px;
                padding: 4px 12px; font-size: 12px; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #3fb950;
              animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
main { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
h2 { font-size: 20px; font-weight: 600; margin-bottom: 24px; color: #e6edf3; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 32px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
.card h3 { font-size: 12px; font-weight: 500; color: #7d8590; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.card .value { font-size: 28px; font-weight: 700; color: #58a6ff; }
.card .sub { font-size: 13px; color: #7d8590; margin-top: 6px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.info-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
.info-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; color: #58a6ff; }
.info-row { display: flex; justify-content: space-between; padding: 8px 0;
            border-bottom: 1px solid #21262d; font-size: 13px; }
.info-row:last-child { border-bottom: none; }
.info-row .label { color: #7d8590; }
.info-row .val { color: #e6edf3; font-weight: 500; }
.actions { display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; }
.btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer;
       font-size: 14px; font-weight: 500; text-decoration: none; transition: all 0.2s; }
.btn-primary { background: #1f6feb; color: white; }
.btn-primary:hover { background: #388bfd; }
.btn-secondary { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
.btn-secondary:hover { background: #30363d; }
.btn-danger { background: #da3633; color: white; }
.providers { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.badge { padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
.badge-green { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
.badge-gray { background: rgba(125,133,144,0.15); color: #7d8590; border: 1px solid rgba(125,133,144,0.3); }
.section { margin-bottom: 32px; }
.memories-list { background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
.memory-item { padding: 14px 20px; border-bottom: 1px solid #21262d; display: flex; gap: 12px; align-items: flex-start; }
.memory-item:last-child { border-bottom: none; }
.memory-key { font-weight: 600; font-size: 13px; color: #58a6ff; min-width: 120px; }
.memory-val { font-size: 13px; color: #7d8590; flex: 1; }
.empty { padding: 32px; text-align: center; color: #7d8590; font-size: 14px; }
</style>
</head>
<body>
<nav>
  <div class="logo"><div class="logo-icon">P</div> Prime</div>
  <a href="/" class="active">Dashboard</a>
  <a href="/chat">Chat</a>
  <div class="nav-right">
    <div class="status-badge"><div class="status-dot"></div><span id="uptime">-</span></div>
  </div>
</nav>
<main>
  <div class="grid" id="stats">
    <div class="card"><h3>Sessions</h3><div class="value" id="s-sessions">-</div><div class="sub">total conversations</div></div>
    <div class="card"><h3>Messages</h3><div class="value" id="s-messages">-</div><div class="sub">total messages</div></div>
    <div class="card"><h3>Memories</h3><div class="value" id="s-memories">-</div><div class="sub">saved facts</div></div>
    <div class="card"><h3>Tasks</h3><div class="value" id="s-tasks">-</div><div class="sub">scheduled tasks</div></div>
  </div>

  <div class="info-grid section">
    <div class="info-card">
      <h3>System Info</h3>
      <div id="sysinfo"><div class="info-row"><span class="label">Loading...</span></div></div>
    </div>
    <div class="info-card">
      <h3>AI Providers</h3>
      <div id="providers-list"><div class="info-row"><span class="label">Loading...</span></div></div>
      <div class="actions">
        <a href="/chat" class="btn btn-primary">Open Chat</a>
        <button class="btn btn-secondary" onclick="window.location.reload()">Refresh</button>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Recent Memories</h2>
    <div class="memories-list" id="memories-list"><div class="empty">Loading...</div></div>
  </div>
</main>

<script>
async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();

    document.getElementById('uptime').textContent = 'Uptime: ' + d.uptime;
    document.getElementById('s-sessions').textContent = d.db.sessions ?? 0;
    document.getElementById('s-messages').textContent = d.db.messages ?? 0;
    document.getElementById('s-memories').textContent = d.db.memories ?? 0;
    document.getElementById('s-tasks').textContent = d.db.active_tasks ?? 0;

    const sys = d.system;
    document.getElementById('sysinfo').innerHTML = `
      <div class="info-row"><span class="label">Hostname</span><span class="val">${sys.hostname}</span></div>
      <div class="info-row"><span class="label">OS</span><span class="val">${sys.os}</span></div>
      <div class="info-row"><span class="label">Environment</span><span class="val">${sys.environment}</span></div>
      <div class="info-row"><span class="label">User</span><span class="val">${sys.user}</span></div>
      <div class="info-row"><span class="label">Workspace</span><span class="val" style="font-size:11px">${sys.workspace}</span></div>
    `;

    const all = ['deepseek','kimi','gemini','openai','anthropic','claude-code'];
    const active = d.providers || [];
    const best = d.provider || 'none';
    document.getElementById('providers-list').innerHTML = all.map(p => `
      <div class="info-row">
        <span class="label">${p}</span>
        <span class="badge ${active.includes(p) ? 'badge-green' : 'badge-gray'}">
          ${active.includes(p) ? (p === best ? 'active (primary)' : 'available') : 'no key'}
        </span>
      </div>
    `).join('');
  } catch(e) {
    console.error('Stats error:', e);
  }
}

async function loadMemories() {
  try {
    const r = await fetch('/api/memories');
    const mems = await r.json();
    const el = document.getElementById('memories-list');
    if (!mems.length) {
      el.innerHTML = '<div class="empty">No memories yet. Chat with Prime to save facts!</div>';
      return;
    }
    el.innerHTML = mems.slice(0,15).map(m => `
      <div class="memory-item">
        <div class="memory-key">${m.key}</div>
        <div class="memory-val">${m.content.slice(0, 200)}</div>
      </div>
    `).join('');
  } catch(e) {}
}

loadStats();
loadMemories();
setInterval(loadStats, 10000);
</script>
</body>
</html>"""
