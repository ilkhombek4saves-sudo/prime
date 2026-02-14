"""Core agent loop — orchestrates LLM calls, tool execution, and memory"""
from __future__ import annotations

import json
import os
import platform
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from prime.config.settings import settings, CONFIG_DIR
from prime.core.tools import ToolExecutor
from prime.core.providers import LLMProvider


# ─── Colors (for CLI output) ─────────────────────────────────────────────────
R = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[91m"; GRN = "\033[92m"; YLW = "\033[93m"; BLU = "\033[94m"; CYN = "\033[96m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}")


# ─── System Info ──────────────────────────────────────────────────────────────
def get_system_info() -> dict:
    info = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "workspace": settings.WORKSPACE,
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


# ─── System Prompt ────────────────────────────────────────────────────────────
def build_system_prompt(user_memories: str = "") -> str:
    info = get_system_info()
    apis = settings.available_providers()
    api_list = ", ".join(apis) if apis else "none configured"

    memory_section = ""
    if user_memories:
        memory_section = f"\n## User Memory\n{user_memories}\n"

    return f"""You are Prime, a production AI agent running on a REAL machine with FULL ACCESS to the local filesystem, shell, and network.

You are NOT ChatGPT, NOT OpenAI, NOT Claude by default — you are **Prime**, a self-hosted AI agent similar to OpenClaw.

## Your Environment
- Hostname: {info['hostname']}
- OS: {info['os']}
- Environment: {info['environment']}
- User: {info['user']}
- Working directory: {info['workspace']}
- Python: {info['python']}
- Configured APIs: {api_list}
- Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{memory_section}
## CRITICAL: YOU MUST USE TOOLS
When the user asks about files, directories, or system state — call the appropriate tool immediately. Never say you cannot access files.

### Tool Usage Rules:
- "what files" / "list directory" → CALL list_files tool
- "read file" / "show file content" → CALL read_file tool
- "run command" / "execute" → CALL exec tool
- "remember" / "save this" → CALL memory_save tool
- "what did I say about" → CALL memory_search tool

### ABSOLUTE RULES:
1. NEVER say "I cannot access your filesystem" — you DO have access via tools.
2. ALWAYS call the appropriate tool when asked about files or system.
3. You are running ON THE MACHINE — you can read files, run commands, access everything.
4. Answer in the same language as the user's question.
5. You are Prime — a helpful, capable, and direct AI agent."""


# ─── Agent Loop ───────────────────────────────────────────────────────────────
REFUSE_PHRASES = (
    "не могу", "не имею доступа", "i cannot", "i can't", "i don't have access",
    "no access", "unable to access", "cannot access", "не могу получить",
    "i'm a text ai", "text-based ai",
)


class Agent:
    """Core agent: LLM + tools + memory + multi-turn conversation."""

    MAX_TURNS = 15

    def __init__(
        self,
        session_id: str = "default",
        provider: str = None,
        model: str = None,
        workspace: str = None,
        channel: str = "cli",
        user_id: str = None,
    ):
        self.session_id = session_id
        self.channel = channel
        self.user_id = user_id
        self.provider_obj = LLMProvider(provider=provider, model=model)
        self.executor = ToolExecutor(workspace=workspace or settings.WORKSPACE)
        self._messages: list[dict] = []
        self._initialized = False

    def _init_session(self):
        """Load or create session, build system prompt with memory context."""
        if self._initialized:
            return
        try:
            from prime.core.memory import get_db
            db = get_db()
            db.create_session(self.session_id, self.channel, self.user_id)
            history = db.get_conversation(self.session_id, limit=20)

            # Load relevant memories for context
            mem_context = ""
            if self.user_id:
                mems = db.list_memories(self.user_id)
                if mems:
                    mem_lines = [f"- {m['key']}: {m['content'][:200]}" for m in mems[:10]]
                    mem_context = "\n".join(mem_lines)

            self._messages = [{"role": "system", "content": build_system_prompt(mem_context)}]
            self._messages.extend(history)
        except Exception:
            self._messages = [{"role": "system", "content": build_system_prompt()}]
        self._initialized = True

    def _execute_tools(self, tool_calls: list) -> list[str]:
        """Execute tool calls and return results."""
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
            short_args = ", ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
            log(f"Tool: {name}({short_args})")
            result = self.executor.execute(name, args)
            results.append(result)
        return results

    def _save_turn(self, user_msg: str, assistant_msg: str):
        """Persist conversation turn to database."""
        try:
            from prime.core.memory import get_db
            db = get_db()
            db.add_message(self.session_id, "user", user_msg)
            db.add_message(self.session_id, "assistant", assistant_msg)
        except Exception:
            pass

    def chat(self, user_message: str) -> str:
        """Process a single message and return the response."""
        self._init_session()
        log(f"Provider: {self.provider_obj.provider} ({self.provider_obj.model})")

        self._messages.append({"role": "user", "content": user_message})

        response = ""
        for _turn in range(self.MAX_TURNS):
            content, tool_calls, raw_msg = self.provider_obj.call(self._messages)

            # Error response
            if isinstance(content, str) and not tool_calls and content.startswith("Error"):
                self._messages.pop()  # Remove the user message we just added
                self._messages.append({"role": "user", "content": user_message})
                return content

            # Guard: model refuses to use tools
            if not tool_calls and isinstance(content, str):
                lower = content.lower()
                if any(p in lower for p in REFUSE_PHRASES):
                    self._messages.append({
                        "role": "user",
                        "content": "You MUST use tools to answer. Call list_files or exec now.",
                    })
                    continue

            if not tool_calls:
                response = content
                self._messages.append({"role": "assistant", "content": content})
                break

            results = self._execute_tools(tool_calls)
            self.provider_obj.append_tool_results(self._messages, raw_msg, tool_calls, results)

        if not response:
            response = "Reached maximum turns. Try a more specific question."

        self._save_turn(user_message, response)
        return response

    def reset(self):
        """Clear conversation history (keep system prompt)."""
        self._initialized = False
        self._messages = []


class InteractiveSession:
    """Interactive CLI session with persistent conversation."""

    def __init__(self, provider: str = None, model: str = None, workspace: str = None):
        import uuid
        self.agent = Agent(
            session_id=f"cli-{uuid.uuid4().hex[:8]}",
            provider=provider,
            model=model,
            workspace=workspace,
            channel="cli",
        )

    def run(self):
        """Start interactive REPL."""
        agent = self.agent
        agent._init_session()
        p = agent.provider_obj

        print(f"\n{BOLD}{CYN}Prime Agent — Interactive Mode{R}")
        print(f"{DIM}Provider: {p.provider} ({p.model}) | Type 'exit' to quit{R}\n")

        while True:
            try:
                query = input(f"{CYN}>> {R}").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit", "q"):
                    break
                if query.lower() == "reset":
                    agent.reset()
                    ok("Conversation reset.")
                    continue

                response = agent.chat(query)
                print(f"\n{response}\n")

            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break
