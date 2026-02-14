"""WebChat integration — simple WebSocket chat served via Gateway"""
from __future__ import annotations

# WebChat is handled directly in prime/gateway/server.py via WebSocket endpoint /ws/{session_id}
# This module provides the HTML/JS served to clients

WEBCHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prime — AI Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #e6edf3; height: 100vh; display: flex; flex-direction: column; }
  header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 24px;
           display: flex; align-items: center; gap: 12px; }
  .logo { width: 32px; height: 32px; background: linear-gradient(135deg, #58a6ff, #a371f7);
          border-radius: 8px; display: flex; align-items: center; justify-content: center;
          font-weight: bold; font-size: 14px; }
  header h1 { font-size: 18px; font-weight: 600; }
  .status { margin-left: auto; font-size: 12px; color: #7d8590; display: flex; align-items: center; gap: 6px; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; }
  .status-dot.offline { background: #da3633; }
  #messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .msg { display: flex; gap: 12px; max-width: 85%; }
  .msg.user { flex-direction: row-reverse; align-self: flex-end; }
  .avatar { width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0; display: flex;
            align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
  .msg.assistant .avatar { background: linear-gradient(135deg, #58a6ff, #a371f7); }
  .msg.user .avatar { background: #21262d; }
  .bubble { padding: 12px 16px; border-radius: 12px; line-height: 1.6; font-size: 14px; }
  .msg.assistant .bubble { background: #161b22; border: 1px solid #30363d; border-radius: 12px 12px 12px 4px; }
  .msg.user .bubble { background: #1f6feb; border-radius: 12px 12px 4px 12px; }
  .bubble pre { background: #0d1117; padding: 12px; border-radius: 6px; overflow-x: auto;
                font-size: 13px; margin: 8px 0; }
  .bubble code { font-family: 'SF Mono', 'Fira Code', monospace; }
  .thinking { display: flex; gap: 4px; align-items: center; padding: 8px; }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: #58a6ff;
         animation: bounce 1.2s ease-in-out infinite; }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-8px); } }
  #input-area { padding: 16px 24px; background: #161b22; border-top: 1px solid #30363d; }
  #form { display: flex; gap: 12px; }
  #input { flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
           padding: 12px 16px; color: #e6edf3; font-size: 14px; resize: none; min-height: 44px;
           max-height: 120px; outline: none; font-family: inherit; }
  #input:focus { border-color: #58a6ff; }
  #send { background: #1f6feb; border: none; border-radius: 8px; padding: 12px 20px;
          color: white; cursor: pointer; font-size: 14px; font-weight: 500; white-space: nowrap; }
  #send:hover { background: #388bfd; }
  #send:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <div class="logo">P</div>
  <h1>Prime Agent</h1>
  <div class="status" id="status">
    <div class="status-dot offline" id="dot"></div>
    <span id="status-text">Connecting...</span>
  </div>
</header>
<div id="messages">
  <div class="msg assistant">
    <div class="avatar">P</div>
    <div class="bubble">👋 Привет! Я Prime — AI-агент с доступом к серверу. Чем помочь?</div>
  </div>
</div>
<div id="input-area">
  <form id="form">
    <textarea id="input" placeholder="Напишите сообщение..." rows="1"></textarea>
    <button type="submit" id="send">Отправить</button>
  </form>
</div>
<script>
const msgs = document.getElementById('messages');
const input = document.getElementById('input');
const send = document.getElementById('send');
const dot = document.getElementById('dot');
const statusText = document.getElementById('status-text');
const sessionId = 'web-' + Math.random().toString(36).slice(2, 10);

let ws = null;
let thinking = null;

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/${sessionId}`);

  ws.onopen = () => {
    dot.classList.remove('offline');
    statusText.textContent = 'Online';
  };

  ws.onclose = () => {
    dot.classList.add('offline');
    statusText.textContent = 'Disconnected';
    setTimeout(connect, 3000);
  };

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'status' && data.content === 'thinking') {
      showThinking();
    } else if (data.type === 'message') {
      hideThinking();
      addMsg('assistant', data.content);
      send.disabled = false;
    }
  };
}

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const label = role === 'user' ? '👤' : 'P';
  const formatted = text.replace(/```(\\w*)\\n?([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>')
                        .replace(/`([^`]+)`/g, '<code>$1</code>')
                        .replace(/\\n/g, '<br>');
  div.innerHTML = `<div class="avatar">${label}</div><div class="bubble">${formatted}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function showThinking() {
  if (thinking) return;
  thinking = document.createElement('div');
  thinking.className = 'msg assistant';
  thinking.innerHTML = '<div class="avatar">P</div><div class="bubble"><div class="thinking"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
  msgs.appendChild(thinking);
  msgs.scrollTop = msgs.scrollHeight;
}

function hideThinking() {
  if (thinking) { thinking.remove(); thinking = null; }
}

document.getElementById('form').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  addMsg('user', text);
  ws.send(JSON.stringify({ message: text }));
  input.value = '';
  input.style.height = 'auto';
  send.disabled = true;
});

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    document.getElementById('form').dispatchEvent(new Event('submit'));
  }
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

connect();
</script>
</body>
</html>"""
