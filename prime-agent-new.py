#!/usr/bin/env python3
"""
Prime Agent — OpenClaw-compatible AI Agent
Full tool-calling, sessions, memory, cron, browser support
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Setup paths
PRIME_HOME = Path(os.environ.get("PRIME_HOME", Path.home() / ".prime"))
CONFIG_DIR = Path.home() / ".config" / "prime"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = CONFIG_DIR / ".env"
LOG_FILE = CONFIG_DIR / "prime.log"
DB_FILE = CONFIG_DIR / "prime.db"
MEMORY_DIR = PRIME_HOME / "memory"

R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}", file=sys.stderr)


def banner():
    print()
    print(f"{BOLD}{CYN} ██████╗ ██████╗ ██╗███╗   ███╗███████╗{R}")
    print(f"{BOLD}{CYN} ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝{R}")
    print(f"{BOLD}{CYN} ██████╔╝██████╔╝██║██╔████╔██║█████╗  {R}")
    print(f"{BOLD}{CYN} ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  {R}")
    print(f"{BOLD}{CYN} ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗{R}")
    print(f"{BOLD}{CYN} ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝{R}")
    print(f"{DIM}    Agent Mode — OpenClaw Compatible{R}")
    print()


# Tool definitions (OpenAI format)
TOOLS = [
    {"type": "function", "function": {"name": "read", "description": "Read file contents. Supports text and images.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["file_path"]}}},
    {"type": "function", "function": {"name": "write", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
    {"type": "function", "function": {"name": "edit", "description": "Edit file by replacing exact text.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "oldText": {"type": "string"}, "newText": {"type": "string"}}, "required": ["file_path", "oldText", "newText"]}}},
    {"type": "function", "function": {"name": "exec", "description": "Execute shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "Search the web using DuckDuckGo.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "web_fetch", "description": "Fetch URL content.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "maxChars": {"type": "integer"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "memory_search", "description": "Search memory files.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "maxResults": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "sessions_list", "description": "List sessions.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "cron_add", "description": "Add cron job.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "schedule": {"type": "string"}, "text": {"type": "string"}}, "required": ["name", "schedule", "text"]}}},
]


class ToolExecutor:
    def __init__(self, workspace_path):
        self.workspace = Path(workspace_path).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path):
        if path.startswith('/'):
            return Path(path)
        return (self.workspace / path).resolve()

    def read(self, file_path, offset=None, limit=None):
        try:
            p = self._safe_path(file_path)
            if not p.exists():
                return f"Error: File not found: {file_path}"
            content = p.read_text(encoding='utf-8', errors='replace')
            lines = content.splitlines()
            if offset: lines = lines[max(0, offset-1):]
            if limit: lines = lines[:limit]
            result = '\n'.join(lines)
            return result[:50000] + ("\n...[truncated]" if len(result) > 50000 else "")
        except Exception as e:
            return f"Error: {e}"

    def write(self, file_path, content):
        try:
            p = self._safe_path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            return f"OK: Written {file_path} ({len(content)} chars)"
        except Exception as e:
            return f"Error: {e}"

    def edit(self, file_path, oldText, newText):
        try:
            p = self._safe_path(file_path)
            content = p.read_text(encoding='utf-8')
            if oldText not in content:
                return "Error: oldText not found"
            new_content = content.replace(oldText, newText, 1)
            p.write_text(new_content, encoding='utf-8')
            return f"OK: Edited {file_path}"
        except Exception as e:
            return f"Error: {e}"

    def exec(self, command, timeout=60):
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=str(self.workspace), timeout=timeout)
            out = (r.stdout + r.stderr).strip()
            return out[:10000] + ("\n...[truncated]" if len(out) > 10000 else "") or "(no output)"
        except Exception as e:
            return f"Error: {e}"

    def web_search(self, query, count=5):
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(count, 10)))
            if not results: return "No results."
            lines = [f"Search: {query}"]
            for r in results:
                lines.append(f"\n- {r.get('title')}\n  {r.get('body', '')[:150]}...\n  {r.get('href')}")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error: {e}"

    def web_fetch(self, url, maxChars=8000):
        try:
            import httpx, re
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            text = re.sub(r'<script.*?</script>', '', resp.text, flags=re.S)
            text = re.sub(r'<style.*?</style>', '', text, flags=re.S)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:maxChars]
        except Exception as e:
            return f"Error: {e}"

    def memory_search(self, query, maxResults=5):
        try:
            files = []
            mf = self.workspace / "MEMORY.md"
            if mf.exists(): files.append(mf)
            md = self.workspace / "memory"
            if md.exists(): files.extend(md.glob("*.md"))
            if not files: return "No memory files."
            
            results = []
            q = query.lower()
            for f in files:
                content = f.read_text(errors='ignore')
                matches = [(i+1, line[:150]) for i, line in enumerate(content.splitlines()) if q in line.lower()]
                if matches:
                    results.append((str(f.relative_to(self.workspace)), matches[:3]))
            
            lines = [f"Memory: '{query}'"]
            for path, matches in results[:maxResults]:
                lines.append(f"\n{path}:")
                for ln, text in matches:
                    lines.append(f"  {ln}: {text}")
            return '\n'.join(lines) if len(lines) > 1 else "No matches."
        except Exception as e:
            return f"Error: {e}"

    def sessions_list(self):
        return "Main session active."

    def cron_add(self, name, schedule, text):
        try:
            cf = CONFIG_DIR / "cron_jobs.json"
            jobs = json.loads(cf.read_text()) if cf.exists() else []
            jobs.append({"name": name, "schedule": schedule, "text": text, "created": time.time(), "enabled": True})
            cf.write_text(json.dumps(jobs, indent=2))
            return f"Cron: Added '{name}'"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, name, arguments):
        method = getattr(self, name, None)
        if method:
            try:
                return method(**arguments)
            except Exception as e:
                return f"Error: {e}"
        return f"Unknown: {name}"


class AgentRunner:
    def __init__(self, model="llama3.2", workspace="."):
        self.model = model
        self.workspace = workspace
        self.executor = ToolExecutor(workspace)
        self.max_turns = 10

    def chat(self, user_message):
        messages = [
            {"role": "system", "content": f"You are Prime, an AI assistant with tools. Use tools when needed. Workspace: {self.workspace}"},
            {"role": "user", "content": user_message}
        ]
        
        for turn in range(self.max_turns):
            resp = self._call_ollama(messages)
            if "error" in resp:
                return f"Error: {resp['error']}"
            
            msg = resp.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            
            if tool_calls:
                messages.append(msg)
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                    
                    log(f"Tool: {name}")
                    result = self.executor.execute(name, args)
                    messages.append({"role": "tool", "content": result})
            else:
                return content
        
        return "Max turns reached."

    def _call_ollama(self, messages):
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps({"model": self.model, "messages": messages, "tools": TOOLS, "stream": False}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return {"message": json.loads(r.read().decode())}
        except Exception as e:
            return {"error": str(e)}


def check_ollama():
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except:
        return False


def cmd_agent(args):
    if not args.message:
        error("No message. Use: prime agent 'hello'")
        return
    
    if not check_ollama():
        error("Ollama not running. Start: ollama serve")
        return
    
    model = args.model or "llama3.2"
    workspace = os.environ.get("PRIME_WORKSPACE", os.getcwd())
    
    runner = AgentRunner(model, workspace)
    log(f"Prime -> {model}")
    print()
    
    try:
        response = runner.chat(args.message)
        print(response)
        print()
    except Exception as e:
        error(f"Failed: {e}")
        import traceback
        traceback.print_exc()


def cmd_status(args):
    banner()
    if CONFIG_FILE.exists():
        ok(f"Config: {CONFIG_FILE}")
    else:
        error("Not initialized. Run: prime init")
        return
    
    if check_ollama():
        models = get_ollama_models()
        ok(f"Ollama: {len(models)} models")
        for m in models[:3]:
            print(f"       - {m}")
    else:
        error("Ollama not running")


def get_ollama_models():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except:
        return []


def main():
    parser = argparse.ArgumentParser(prog="prime", description="Prime Agent")
    sub = parser.add_subparsers(dest="cmd")
    
    agent = sub.add_parser("agent", help="Chat with agent")
    agent.add_argument("message", help="Message to send")
    agent.add_argument("--model", help="Model to use")
    
    sub.add_parser("status", help="Check status")
    
    args = parser.parse_args()
    
    if args.cmd == "agent":
        cmd_agent(args)
    elif args.cmd == "status":
        cmd_status(args)
    else:
        banner()
        parser.print_help()


if __name__ == "__main__":
    main()
