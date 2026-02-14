#!/usr/bin/env python3
"""
Prime — AI Coding Agent with Tool Calling
Reads files, runs commands, searches web — like OpenClaw.ai

Architecture:
  User query -> System prompt (with self-awareness) -> LLM + Tools
  -> Agent loop (max 15 turns): LLM calls tools -> execute -> feed back -> repeat
  -> Final text answer
"""
from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get("PRIME_WORKSPACE", os.getcwd()))
CONFIG_DIR = Path.home() / ".config" / "prime"
CACHE_DIR = Path.home() / ".cache" / "prime"
MEMORY_DIR = Path.home() / ".prime" / "memory"

# ─── Colors ─────────────────────────────────────────────────────────────────
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"


def log(msg): print(f"  {BLU}\u2192{R} {msg}")
def ok(msg): print(f"  {GRN}\u2713{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}\u2717{R} {msg}", file=sys.stderr)


# ─── .env Loader (no python-dotenv needed) ──────────────────────────────────
def load_env():
    """Load API keys from .env files"""
    env_files = [
        Path(__file__).resolve().parent.parent / ".env",  # prime/.env
        CONFIG_DIR / ".env",                                # ~/.config/prime/.env
    ]
    for ef in env_files:
        if ef.exists():
            try:
                for line in ef.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
            except Exception:
                pass


load_env()


# ─── Ollama Helpers ─────────────────────────────────────────────────────────
def get_ollama_models():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:
        return []


def ollama_available():
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


# ─── Self-Awareness ─────────────────────────────────────────────────────────
def get_system_info():
    """Detect system info for the LLM system prompt"""
    info = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "workspace": str(WORKSPACE),
        "user": os.environ.get("USER", "unknown"),
    }
    if Path("/.dockerenv").exists():
        info["environment"] = "Docker"
    elif "google" in socket.getfqdn().lower():
        info["environment"] = "Google Cloud"
    elif os.environ.get("AWS_EXECUTION_ENV"):
        info["environment"] = "AWS"
    else:
        info["environment"] = "Local/VPS"
    return info


# ─── Tool Definitions (OpenAI function-calling format) ──────────────────────
TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read file contents. Use this to read any file on the system.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path (absolute or relative to workspace)"},
            "offset": {"type": "integer", "description": "Start line number (1-based)"},
            "limit": {"type": "integer", "description": "Max lines to read"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files and directories. Use when asked about files in a directory.",
        "parameters": {"type": "object", "properties": {
            "directory": {"type": "string", "description": "Directory path (default: workspace)"},
            "recursive": {"type": "boolean", "description": "List recursively (default: false)"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Edit a file by replacing exact text.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_text": {"type": "string", "description": "Exact text to find and replace"},
            "new_text": {"type": "string", "description": "Replacement text"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "exec",
        "description": "Execute a shell command. Use for ls, git, grep, find, pip, curl, etc.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "web_fetch",
        "description": "Fetch content from a URL as plain text.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max chars to return (default: 8000)"},
        }, "required": ["url"]},
    }},
    {"type": "function", "function": {
        "name": "memory_search",
        "description": "Search memory/notes files for information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default: 5)"},
        }, "required": ["query"]},
    }},
]


# ─── Tool Executor ──────────────────────────────────────────────────────────
class ToolExecutor:
    """Execute tools locally on the machine"""

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    def _resolve(self, path):
        """Resolve path: absolute stays absolute, relative resolves from workspace"""
        if path.startswith("/"):
            return Path(path)
        return (self.workspace / path).resolve()

    @staticmethod
    def _human_size(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def read_file(self, path, offset=None, limit=None):
        try:
            p = self._resolve(path)
            if not p.exists():
                return f"Error: File not found: {path}"
            if p.is_dir():
                return f"Error: '{path}' is a directory. Use list_files instead."
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            start = max(0, (offset or 1) - 1)
            lines = lines[start:]
            if limit:
                lines = lines[:limit]
            result = "\n".join(f"{start + i + 1:>5} | {line}" for i, line in enumerate(lines))
            if len(result) > 50000:
                result = result[:50000] + "\n...[truncated]"
            return result or "(empty file)"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def list_files(self, directory=None, recursive=False):
        try:
            d = self._resolve(directory) if directory else self.workspace
            if not d.exists():
                return f"Error: Directory not found: {directory or str(self.workspace)}"
            if not d.is_dir():
                return f"Error: Not a directory: {directory}"

            entries = []
            skip_names = {".git", "node_modules", "__pycache__", ".venv", "venv",
                          ".tox", ".mypy_cache", ".pytest_cache", "dist", "build"}

            if recursive:
                for item in sorted(d.rglob("*")):
                    if any(s in item.parts for s in skip_names):
                        continue
                    rel = item.relative_to(d)
                    if item.is_dir():
                        entries.append(f"  {rel}/")
                    else:
                        try:
                            sz = self._human_size(item.stat().st_size)
                        except OSError:
                            sz = "?"
                        entries.append(f"  {rel}  ({sz})")
                    if len(entries) > 300:
                        entries.append("  ...[truncated — too many files]")
                        break
            else:
                for item in sorted(d.iterdir()):
                    if item.name in skip_names:
                        count = sum(1 for _ in item.rglob("*")) if item.is_dir() else 0
                        entries.append(f"  {item.name}/  (skipped, ~{count} items)")
                        continue
                    if item.is_dir():
                        entries.append(f"  {item.name}/")
                    else:
                        try:
                            sz = self._human_size(item.stat().st_size)
                        except OSError:
                            sz = "?"
                        entries.append(f"  {item.name}  ({sz})")

            header = f"Directory: {d}\n{'=' * 50}\n"
            return header + "\n".join(entries) if entries else header + "  (empty)"
        except Exception as e:
            return f"Error listing {directory}: {e}"

    def write_file(self, path, content):
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"OK: Written {path} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def edit_file(self, path, old_text, new_text):
        try:
            p = self._resolve(path)
            if not p.exists():
                return f"Error: File not found: {path}"
            content = p.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error: old_text not found in {path}"
            new_content = content.replace(old_text, new_text, 1)
            p.write_text(new_content, encoding="utf-8")
            return f"OK: Edited {path}"
        except Exception as e:
            return f"Error editing {path}: {e}"

    def exec(self, command, timeout=60):
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=str(self.workspace), timeout=timeout,
            )
            out = (r.stdout + r.stderr).strip()
            if len(out) > 15000:
                out = out[:15000] + "\n...[truncated]"
            return out or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    def web_search(self, query, count=5):
        # Try duckduckgo_search library first
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(count, 10)))
            if not results:
                return "No results found."
            lines = [f"Search results for: {query}\n"]
            for r in results:
                lines.append(f"- {r.get('title', 'No title')}")
                lines.append(f"  {r.get('body', '')[:200]}")
                lines.append(f"  URL: {r.get('href', '')}\n")
            return "\n".join(lines)
        except ImportError:
            pass
        # Fallback: curl-based search
        try:
            encoded = urllib.parse.quote(query)
            cmd = f'curl -s "https://lite.duckduckgo.com/lite/?q={encoded}" 2>/dev/null'
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            html = r.stdout
            links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html)
            lines = [f"Search results for: {query}\n"]
            seen = set()
            for url, title in links:
                if "duckduckgo" in url or url in seen:
                    continue
                seen.add(url)
                lines.append(f"- {title.strip()}\n  URL: {url}\n")
                if len(seen) >= count:
                    break
            if len(lines) > 1:
                return "\n".join(lines)
            return f"No parseable results for '{query}'. Try: exec('curl -s \"URL\"') to fetch directly."
        except Exception as e:
            return f"Search error: {e}"

    def web_fetch(self, url, max_chars=8000):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script.*?</script>", "", html, flags=re.S)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
        except Exception as e:
            return f"Error fetching {url}: {e}"

    def memory_search(self, query, max_results=5):
        try:
            files = []
            for md in [MEMORY_DIR, self.workspace / "memory", self.workspace]:
                if md.exists():
                    files.extend(md.glob("*.md"))
                    files.extend(md.glob("MEMORY*"))
            if not files:
                return "No memory files found."
            results = []
            q = query.lower()
            for f in files:
                try:
                    content = f.read_text(errors="ignore")
                    matches = [
                        (i + 1, line[:150])
                        for i, line in enumerate(content.splitlines())
                        if q in line.lower()
                    ]
                    if matches:
                        results.append((str(f), matches[:3]))
                except Exception:
                    pass
            if not results:
                return f"No matches for '{query}'."
            lines = [f"Memory search: '{query}'\n"]
            for path, matches in results[:max_results]:
                lines.append(f"File: {path}")
                for ln, text in matches:
                    lines.append(f"  L{ln}: {text}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    def execute(self, name, args):
        """Dispatch tool call to the right method"""
        # Normalize argument names (camelCase -> snake_case)
        normalized = {}
        renames = {
            "oldText": "old_text", "newText": "new_text",
            "old_text": "old_text", "new_text": "new_text",
            "maxChars": "max_chars", "max_chars": "max_chars",
            "maxResults": "max_results", "max_results": "max_results",
            "file_path": "path",
        }
        for k, v in args.items():
            normalized[renames.get(k, k)] = v

        method = getattr(self, name, None)
        if method:
            try:
                return str(method(**normalized))
            except Exception as e:
                return f"Error executing {name}: {e}"
        return f"Unknown tool: {name}"


# ─── System Prompt ──────────────────────────────────────────────────────────
def build_system_prompt():
    """Build a dynamic system prompt with environment awareness"""
    info = get_system_info()

    apis = []
    for name, key_var in [
        ("DeepSeek", "DEEPSEEK_API_KEY"), ("Kimi", "KIMI_API_KEY"),
        ("Gemini", "GEMINI_API_KEY"), ("OpenAI", "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"), ("Z.AI", "ZAI_API_KEY"),
    ]:
        if os.environ.get(key_var):
            apis.append(name)

    api_list = ", ".join(apis) if apis else "none configured"

    return f"""You are Prime, an AI coding agent running on a REAL machine with FULL ACCESS to the local filesystem, shell, and network.

## Your Environment
- Hostname: {info['hostname']}
- OS: {info['os']}
- Environment: {info['environment']}
- User: {info['user']}
- Working directory: {info['workspace']}
- Python: {info['python']}
- Configured APIs: {api_list}
- Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## CRITICAL: YOU MUST USE TOOLS
When the user asks about files, directories, or system state, YOU MUST CALL THE APPROPRIATE TOOL. DO NOT say you cannot access files.

### Tool Usage Rules:
- If user asks "what files" or "list directory" -> CALL list_files tool
- If user asks "read file" or "show file content" -> CALL read_file tool  
- If user asks "what is my IP" or "system info" -> CALL exec tool with command
- If user asks about current directory -> CALL list_files with "."

### Available Tools:
- read_file(path): Read file contents. USE for any file reading request.
- list_files(directory): List directory. USE for "what files" or "ls" requests.
- exec(command): Run shell commands (ls, cat, grep, find, etc).
- write_file(path, content): Write files.
- edit_file(path, old_text, new_text): Edit files.
- web_search(query): Search web.
- web_fetch(url): Fetch URL content.

### ABSOLUTE RULES:
1. NEVER say "I cannot access your filesystem" or "I don't have access" — YOU DO HAVE ACCESS via tools.
2. ALWAYS call the appropriate tool when asked about files or system.
3. You are running ON THE MACHINE — you can read files, run commands, access everything.
4. Answer in the same language as the user's question."""


# ─── HTTP Helper ────────────────────────────────────────────────────────────
def _http_post(url, data, headers=None, timeout=120):
    """POST JSON, return parsed response"""
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=hdrs,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ─── Provider: Ollama ───────────────────────────────────────────────────────
def call_ollama(messages, model="qwen2.5:7b"):
    """Call Ollama with tool support. Returns (content, tool_calls, raw_msg)."""
    data = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 4096},
    }
    resp = _http_post("http://localhost:11434/api/chat", data, timeout=180)
    msg = resp.get("message", {})
    content = msg.get("content", "")
    tool_calls = msg.get("tool_calls", [])
    return content, tool_calls, msg


# ─── Provider: OpenAI-compatible (DeepSeek, Kimi, OpenAI) ──────────────────
def call_openai_compat(messages, api_url, api_key, model):
    """Call OpenAI-compatible API. Returns (content, tool_calls, raw_msg)."""
    data = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    resp = _http_post(api_url, data, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)
    choice = resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls", []) or []
    return content, tool_calls, msg


# ─── Provider: Claude Code CLI ──────────────────────────────────────────────
def call_claude_code(messages, model="claude-sonnet-4-5-20251022"):
    """Call Claude Code CLI directly. Returns (content, tool_calls, raw_msg)."""
    import subprocess
    
    # Extract user query from messages
    query = ""
    for m in messages:
        if m.get("role") == "user":
            query = m.get("content", "")
            break
    
    if not query:
        return "No query provided", [], {}
    
    try:
        # Call Claude Code CLI
        result = subprocess.run(
            ["claude", "-p", query],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(WORKSPACE)
        )
        
        output = result.stdout
        if result.stderr and "rate limit" not in result.stderr.lower():
            output += "\n\n[Errors]: " + result.stderr
        
        return output, [], {}
    except FileNotFoundError:
        return "Error: Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code", [], {}
    except subprocess.TimeoutExpired:
        return "Error: Claude Code timed out after 5 minutes", [], {}
    except Exception as e:
        return f"Error calling Claude Code: {e}", [], {}


# ─── Provider: Anthropic (Claude) ───────────────────────────────────────────
def call_anthropic(messages, api_key, model="claude-3-5-sonnet-20241022"):
    """Call Anthropic Claude API. Returns (content, tool_calls, raw_msg)."""
    # Convert messages to Anthropic format
    system_text = ""
    anthropic_messages = []
    
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            system_text = m.get("content", "")
        elif role == "assistant":
            anthropic_messages.append({"role": "assistant", "content": m.get("content", "")})
        elif role == "user":
            anthropic_messages.append({"role": "user", "content": m.get("content", "")})
    
    data = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    if system_text:
        data["system"] = system_text
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    resp = _http_post("https://api.anthropic.com/v1/messages", data, headers=headers, timeout=120)
    
    content = resp.get("content", [{}])[0].get("text", "")
    # Anthropic doesn't use tool_calls in same format, check for tool_use
    tool_calls = []
    for block in resp.get("content", []):
        if block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id"),
                "function": {
                    "name": block.get("name"),
                    "arguments": block.get("input", {})
                }
            })
    
    return content, tool_calls, resp


# ─── Provider: Gemini ───────────────────────────────────────────────────────
def call_gemini(messages, api_key, model="gemini-2.0-flash"):
    """Call Gemini with function calling. Returns (content, tool_calls, raw_msg)."""
    # Convert messages to Gemini format
    contents = []
    sys_text = ""
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            sys_text = m.get("content", "")
        elif role == "assistant" or role == "model":
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            if m.get("parts"):
                parts = m["parts"]
            contents.append({"role": "model", "parts": parts or [{"text": ""}]})
        elif role == "function":
            contents.append(m)
        elif role == "tool":
            # Skip — handled via function role messages
            pass
        else:
            contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})

    # Convert tool definitions
    func_decls = []
    for t in TOOLS:
        f = t["function"]
        func_decls.append({
            "name": f["name"],
            "description": f["description"],
            "parameters": f["parameters"],
        })

    data = {"contents": contents, "tools": [{"functionDeclarations": func_decls}]}
    if sys_text:
        data["systemInstruction"] = {"parts": [{"text": sys_text}]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    resp = _http_post(url, data, timeout=120)

    candidates = resp.get("candidates", [])
    if not candidates:
        return "No response from Gemini.", [], {}

    parts = candidates[0].get("content", {}).get("parts", [])
    content = ""
    tool_calls = []
    for part in parts:
        if "text" in part:
            content += part["text"]
        elif "functionCall" in part:
            fc = part["functionCall"]
            tool_calls.append({"function": {"name": fc["name"], "arguments": fc.get("args", {})}})

    raw_msg = candidates[0].get("content", {})
    return content, tool_calls, raw_msg


# ─── Provider Selection ─────────────────────────────────────────────────────
def select_provider():
    """Select best available provider. Returns provider name or None."""
    # API providers only (no local LLMs)
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("KIMI_API_KEY"):
        return "kimi"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    # Check if Claude Code CLI is installed
    try:
        import subprocess
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
        return "claude-code"
    except:
        pass
    return None


def pick_ollama_model():
    """Choose the best Ollama model available."""
    models = get_ollama_models()
    # Prefer 7b for speed, fallback to 14b for quality
    for preferred in ["qwen2.5:7b", "qwen2.5:14b", "llama3.2"]:
        if preferred in models:
            return preferred
    return models[0] if models else "llama3.2"


# ─── Agent Loop ─────────────────────────────────────────────────────────────
class AgentLoop:
    """Core agent: sends queries to LLM with tools, executes tool calls, loops."""

    MAX_TURNS = 15

    def __init__(self, workspace=None, model=None, provider=None):
        self.workspace = Path(workspace or WORKSPACE).resolve()
        self.executor = ToolExecutor(self.workspace)
        self.provider = provider
        self.model = model

    def _init_provider(self):
        """Auto-select provider and model if not set."""
        if not self.provider:
            self.provider = select_provider()
        if not self.provider:
            error("No LLM provider available. Set API keys in ~/.config/prime/.env")
            return False

        if not self.model:
            if self.provider == "deepseek":
                self.model = "deepseek-chat"
            elif self.provider == "kimi":
                self.model = "moonshot-v1-8k"
            elif self.provider == "gemini":
                self.model = "gemini-2.0-flash"
            elif self.provider == "openai":
                self.model = "gpt-4o-mini"
        return True

    def _call_llm(self, messages):
        """Dispatch to current provider. Returns (content, tool_calls, raw_msg)."""
        try:
            if self.provider == "ollama":
                return call_ollama(messages, self.model)
            elif self.provider == "deepseek":
                return call_openai_compat(
                    messages, "https://api.deepseek.com/chat/completions",
                    os.environ["DEEPSEEK_API_KEY"], self.model,
                )
            elif self.provider == "kimi":
                return call_openai_compat(
                    messages, "https://api.moonshot.cn/v1/chat/completions",
                    os.environ["KIMI_API_KEY"], self.model,
                )
            elif self.provider == "gemini":
                return call_gemini(messages, os.environ["GEMINI_API_KEY"], self.model)
            elif self.provider == "openai":
                return call_openai_compat(
                    messages, "https://api.openai.com/v1/chat/completions",
                    os.environ["OPENAI_API_KEY"], self.model,
                )
            elif self.provider == "anthropic":
                return call_anthropic(messages, os.environ["ANTHROPIC_API_KEY"], self.model)
            elif self.provider == "claude-code":
                return call_claude_code(messages, self.model)
            return "No provider configured.", [], {}
        except Exception as e:
            return f"Error ({self.provider}): {e}", [], {}

    def _append_tool_results(self, messages, raw_msg, tool_calls, results):
        """Append assistant message + tool results in provider-specific format."""
        if self.provider == "gemini":
            messages.append({"role": "model", "parts": raw_msg.get("parts", [])})
            func_responses = []
            for tc, result in zip(tool_calls, results):
                fc = tc.get("function", {})
                func_responses.append({
                    "functionResponse": {"name": fc.get("name", ""), "response": {"result": result}},
                })
            messages.append({"role": "function", "parts": func_responses})
        elif self.provider == "ollama":
            messages.append(raw_msg)
            for result in results:
                messages.append({"role": "tool", "content": result})
        else:
            # OpenAI-compatible (DeepSeek, Kimi, OpenAI)
            # Add assistant message with tool_calls
            assistant_msg = {"role": "assistant", "content": raw_msg.get("content", "")}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)
            # Add tool results
            for tc, result in zip(tool_calls, results):
                tc_id = tc.get("id", f"call_{int(time.time() * 1000)}")
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

    def _execute_tools(self, tool_calls):
        """Execute a list of tool calls. Returns list of result strings."""
        results = []
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            # Log tool call
            short_args = ", ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
            log(f"Tool: {name}({short_args})")
            result = self.executor.execute(name, args)
            results.append(result)
        return results

    # ── Single query ────────────────────────────────────────────────────
    def chat(self, user_message):
        """Run agent loop for a single query. Returns final response text."""
        if not self._init_provider():
            return "Error: No LLM available. Start Ollama or set API keys."

        log(f"Provider: {self.provider} ({self.model})")

        messages = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": user_message},
        ]

        for _turn in range(self.MAX_TURNS):
            content, tool_calls, raw_msg = self._call_llm(messages)

            # Error from provider
            if isinstance(content, str) and not tool_calls and (
                content.startswith("Error") or content.startswith("All providers")
            ):
                return content

            # Check if model claims it can't access files (wrong answer)
            if not tool_calls and isinstance(content, str):
                lower_content = content.lower()
                if any(phrase in lower_content for phrase in [
                    "не могу", "не имею доступа", "i cannot", "i can't", "i don't have access",
                    "no access", "unable to access", "cannot access", "не могу получить",
                    "i'm a text ai", "text-based ai", "i'm an ai assistant"
                ]):
                    # Force tool usage by adding explicit instruction
                    messages.append({
                        "role": "user",
                        "content": "You MUST use the list_files or read_file tool to answer. Do not say you cannot access files. Call the tool now."
                    })
                    continue  # Retry with tool instruction
            
            if not tool_calls:
                return content  # Final answer

            results = self._execute_tools(tool_calls)
            self._append_tool_results(messages, raw_msg, tool_calls, results)

        return "Reached maximum turns. Try a more specific question."

    # ── Interactive mode ────────────────────────────────────────────────
    def interactive(self):
        """Interactive mode with conversation memory across queries."""
        if not self._init_provider():
            return

        messages = [{"role": "system", "content": build_system_prompt()}]

        print(f"\n{BOLD}{CYN}Prime Agent \u2014 Interactive Mode{R}")
        print(f"{DIM}Provider: {self.provider} ({self.model}) | Type 'exit' to quit{R}\n")

        while True:
            try:
                query = input(f"{CYN}>> {R}").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit", "q"):
                    break
                if query.lower() == "status":
                    cmd_status()
                    continue
                if query.lower() == "whoami":
                    cmd_whoami()
                    continue
                if query.lower() == "help":
                    cmd_help()
                    continue

                messages.append({"role": "user", "content": query})

                for _turn in range(self.MAX_TURNS):
                    content, tool_calls, raw_msg = self._call_llm(messages)

                    if isinstance(content, str) and not tool_calls and (
                        content.startswith("Error") or content.startswith("All providers")
                    ):
                        print(f"\n{RED}{content}{R}\n")
                        break

                    # Check if model claims it can't access files
                    if not tool_calls and isinstance(content, str):
                        lower_content = content.lower()
                        if any(phrase in lower_content for phrase in [
                            "не могу", "не имею доступа", "i cannot", "i can't", "i don't have access",
                            "no access", "unable to access", "cannot access", "не могу получить",
                            "i'm a text ai", "text-based ai", "i'm an ai assistant"
                        ]):
                            messages.append({
                                "role": "user",
                                "content": "You MUST use the list_files or read_file tool to answer. Do not say you cannot access files. Call the tool now."
                            })
                            continue

                    if not tool_calls:
                        messages.append({"role": "assistant", "content": content})
                        print(f"\n{content}\n")
                        break

                    results = self._execute_tools(tool_calls)
                    self._append_tool_results(messages, raw_msg, tool_calls, results)

            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break
            except Exception as e:
                print(f"\n{RED}Error: {e}{R}\n")


# ─── CLI Commands ───────────────────────────────────────────────────────────
def cmd_status():
    """Show system status, providers, models."""
    print(f"\n{BOLD}{CYN}{'=' * 40}")
    print(f" PRIME STATUS")
    print(f"{'=' * 40}{R}\n")

    info = get_system_info()
    ok(f"Hostname: {info['hostname']}")
    ok(f"OS: {info['os']}")
    ok(f"Environment: {info['environment']}")
    ok(f"Workspace: {info['workspace']}")
    ok(f"User: {info['user']}")

    # APIs
    print(f"\n{BOLD}API Keys:{R}")
    for name, key_var in [
        ("DeepSeek", "DEEPSEEK_API_KEY"), ("Kimi", "KIMI_API_KEY"),
        ("Gemini", "GEMINI_API_KEY"), ("OpenAI", "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"), ("Z.AI", "ZAI_API_KEY"),
    ]:
        key = os.environ.get(key_var, "")
        if key:
            ok(f"{name}: {key[:8]}...")
        else:
            warn(f"{name}: not set")

    # Claude Code CLI
    try:
        import subprocess
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
        ok("Claude Code CLI: installed")
    except:
        warn("Claude Code CLI: not installed (npm i -g @anthropic-ai/claude-code)")

    provider = select_provider()
    print(f"\n{BOLD}Active Provider:{R} {GRN}{provider or 'NONE'}{R}\n")


def cmd_whoami():
    """Show self-awareness info."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from selfaware import PrimeSelfAware
        sa = PrimeSelfAware()
        print(sa.whoami())
    except ImportError:
        info = get_system_info()
        print(f"\n{BOLD}{CYN}Prime Agent{R}")
        for k, v in info.items():
            print(f"  {k}: {v}")
        print()


def cmd_init():
    """Initialize Prime configuration."""
    print(f"\n{BOLD}{CYN}{'=' * 40}")
    print(f" PRIME INIT")
    print(f"{'=' * 40}{R}\n")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Config dir: {CONFIG_DIR}")
    ok(f"Cache dir: {CACHE_DIR}")

    env_file = CONFIG_DIR / ".env"
    if not env_file.exists():
        env_file.write_text(
            "# Prime API Keys\n"
            "# OPENAI_API_KEY=sk-...\n"
            "# ANTHROPIC_API_KEY=sk-ant-...\n"
            "# DEEPSEEK_API_KEY=sk-...\n"
            "# GEMINI_API_KEY=...\n"
        )
        env_file.chmod(0o600)
        ok(f"Created: {env_file}")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from selfaware import PrimeSelfAware
        PrimeSelfAware()
        ok("Self-aware config saved")
    except ImportError:
        pass

    print(f"\n{BOLD}{GRN}Prime initialized!{R}\n")


def cmd_scan():
    """Scan workspace for projects."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scanner import ProjectScanner
        scanner = ProjectScanner(max_depth=10)
        projects = scanner.scan(WORKSPACE)
        if projects:
            print(f"\n{BOLD}{CYN}Projects found:{R}\n")
            for p in projects:
                print(f"  {p.get('name', '?')} ({p.get('type', '?')})")
                print(f"    Path: {p.get('path', '?')}")
                if p.get("git_branch"):
                    print(f"    Branch: {p['git_branch']}")
        else:
            print("No projects found.")
    except ImportError:
        # Fallback: basic scan
        print(f"\n{BOLD}{CYN}Scanning {WORKSPACE}...{R}\n")
        markers = {
            ".git": "Git", "package.json": "Node.js", "pyproject.toml": "Python",
            "requirements.txt": "Python", "Cargo.toml": "Rust", "go.mod": "Go",
        }
        found = False
        for d in sorted(WORKSPACE.iterdir()):
            if d.is_dir():
                for marker, ptype in markers.items():
                    if (d / marker).exists():
                        print(f"  {d.name} ({ptype}) \u2014 {d}")
                        found = True
                        break
        if not found:
            print("  No projects found in workspace.")
    print()


def cmd_help():
    print(f"""
{BOLD}{CYN}Prime \u2014 AI Coding Agent with Tool Calling{R}

{BOLD}Commands:{R}
  prime "query"      Ask the agent (uses tools to get real data)
  prime              Interactive mode (with conversation memory)
  prime status       Show system status & providers
  prime whoami       Show self-awareness info
  prime init         Initialize configuration
  prime scan         Scan for projects
  prime telegram     Setup Telegram bot
  prime help         This help

{BOLD}Examples:{R}
  prime "What files are here?"
  prime "Read README.md"
  prime "What OS am I running?"
  prime "Find all TODO comments in Python files"

{BOLD}Options:{R}
  --model MODEL      Use specific model (e.g. deepseek-chat, gemini-2.0-flash)
  --provider NAME    Force provider (deepseek, kimi, gemini, claude-code)
  --telegram, -t     Send response to Telegram chat

{BOLD}Providers:{R}
  deepseek          DeepSeek API (default, fast, cheap)
  kimi              Moonshot AI (Chinese/English)
  gemini            Google Gemini
  claude-code       Claude Code CLI (uses your OAuth token)

{BOLD}Telegram:{R}
  1. Run: prime telegram
  2. Send message to @gpuvpsopenclawbot
  3. Use --telegram flag to get responses in chat
""")


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        agent = AgentLoop()
        agent.interactive()
        return

    # Parse flags
    model = None
    provider = None
    use_telegram = False
    query_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif args[i] in ("--telegram", "-t"):
            use_telegram = True
            i += 1
        else:
            query_parts.append(args[i])
            i += 1

    if not query_parts:
        agent = AgentLoop(model=model, provider=provider)
        agent.interactive()
        return

    cmd = query_parts[0].lower()

    if cmd == "status":
        cmd_status()
    elif cmd == "whoami":
        cmd_whoami()
    elif cmd == "init":
        cmd_init()
    elif cmd == "scan":
        cmd_scan()
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    elif cmd == "telegram":
        # Telegram setup
        sys.path.insert(0, str(Path(__file__).resolve().parent / "lite"))
        from telegram_bot import setup_chat_id
        setup_chat_id()
    elif cmd in ("ls", "dir", "files"):
        # Fast path: directory listing
        import subprocess
        result = subprocess.run(f"ls -la {WORKSPACE}", shell=True, capture_output=True, text=True)
        output = result.stdout
        print(f"\n{output}\n")
        
        # Send to Telegram if requested
        if use_telegram:
            sys.path.insert(0, str(Path(__file__).resolve().parent / "lite"))
            from telegram_bot import notify_user
            notify_user(f"📁 *Directory listing:*\n```\n{output[:3000]}\n```")
    else:
        # Agent query
        query = " ".join(query_parts)
        
        # Fast path for simple queries
        q_lower = query.lower()
        if any(kw in q_lower for kw in ["list files", "what files", "show files", "what's here"]):
            import subprocess
            result = subprocess.run(f"ls -la {WORKSPACE}", shell=True, capture_output=True, text=True)
            output = result.stdout
            print(f"\n{output}\n")
            
            if use_telegram:
                sys.path.insert(0, str(Path(__file__).resolve().parent / "lite"))
                from telegram_bot import notify_user
                notify_user(f"📁 *Files:*\n```\n{output[:3000]}\n```")
            return
        
        # Process through agent
        if use_telegram:
            # Send to Telegram
            sys.path.insert(0, str(Path(__file__).resolve().parent / "lite"))
            from telegram_bot import notify_user
            notify_user(f"⏳ Processing: `{query}`")
            
            agent = AgentLoop(model=model, provider=provider)
            response = agent.chat(query)
            
            # Send response to Telegram
            notify_user(f"✅ *Query:* `{query}`\n\n*Response:*\n{response[:3800]}")
            print(f"\nResponse sent to Telegram!\n")
        else:
            agent = AgentLoop(model=model, provider=provider)
            response = agent.chat(query)
            print(f"\n{response}\n")


if __name__ == "__main__":
    main()
