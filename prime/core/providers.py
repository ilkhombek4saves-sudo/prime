"""Model provider abstraction — DeepSeek, Kimi, Gemini, OpenAI, Anthropic, Claude Code"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from prime.config.settings import settings
from prime.core.tools import TOOL_DEFINITIONS


# ─── HTTP Helper ─────────────────────────────────────────────────────────────
def _http_post(url: str, data: dict, headers: dict = None, timeout: int = 120) -> dict:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), headers=hdrs, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ─── Provider Implementations ─────────────────────────────────────────────────
def call_openai_compat(
    messages: list[dict], api_url: str, api_key: str, model: str
) -> tuple[str, list, dict]:
    """Call any OpenAI-compatible API. Returns (content, tool_calls, raw_msg)."""
    data = {
        "model": model,
        "messages": messages,
        "tools": TOOL_DEFINITIONS,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    resp = _http_post(api_url, data, headers={"Authorization": f"Bearer {api_key}"})
    choice = resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls", []) or []
    return content, tool_calls, msg


def call_anthropic(
    messages: list[dict], api_key: str, model: str = "claude-3-5-sonnet-20241022"
) -> tuple[str, list, dict]:
    """Call Anthropic Claude API. Returns (content, tool_calls, raw_msg)."""
    system_text = ""
    anthropic_messages = []
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            system_text = m.get("content", "")
        elif role in ("assistant", "user"):
            anthropic_messages.append({"role": role, "content": m.get("content", "")})

    data: dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    if system_text:
        data["system"] = system_text

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    resp = _http_post("https://api.anthropic.com/v1/messages", data, headers=headers)
    content = ""
    tool_calls = []
    for block in resp.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id"),
                "function": {"name": block.get("name"), "arguments": block.get("input", {})},
            })
    return content, tool_calls, resp


def call_gemini(
    messages: list[dict], api_key: str, model: str = "gemini-2.0-flash"
) -> tuple[str, list, dict]:
    """Call Gemini with function calling. Returns (content, tool_calls, raw_msg)."""
    contents = []
    sys_text = ""
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            sys_text = m.get("content", "")
        elif role in ("assistant", "model"):
            parts = m.get("parts") or ([{"text": m["content"]}] if m.get("content") else [{"text": ""}])
            contents.append({"role": "model", "parts": parts})
        elif role == "function":
            contents.append(m)
        elif role != "tool":
            contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})

    func_decls = [
        {"name": t["function"]["name"], "description": t["function"]["description"],
         "parameters": t["function"]["parameters"]}
        for t in TOOL_DEFINITIONS
    ]
    data: dict[str, Any] = {
        "contents": contents,
        "tools": [{"functionDeclarations": func_decls}],
    }
    if sys_text:
        data["systemInstruction"] = {"parts": [{"text": sys_text}]}

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    resp = _http_post(url, data)

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


def call_claude_code(messages: list[dict]) -> tuple[str, list, dict]:
    """Call Claude Code CLI. Returns (content, [], {})."""
    query = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    if not query:
        return "No query provided", [], {}
    try:
        result = subprocess.run(
            ["claude", "-p", query],
            capture_output=True, text=True, timeout=300,
            cwd=settings.WORKSPACE,
        )
        output = result.stdout
        if result.stderr and "rate limit" not in result.stderr.lower():
            output += "\n\n[stderr]: " + result.stderr
        return output, [], {}
    except FileNotFoundError:
        return "Error: Claude Code CLI not installed.", [], {}
    except subprocess.TimeoutExpired:
        return "Error: Claude Code timed out.", [], {}
    except Exception as e:
        return f"Error calling Claude Code: {e}", [], {}


# ─── Provider Registry ────────────────────────────────────────────────────────
PROVIDER_CONFIGS = {
    "deepseek": {
        "api_url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "kimi": {
        "api_url": "https://api.moonshot.cn/v1/chat/completions",
        "default_model": "moonshot-v1-8k",
        "key_env": "KIMI_API_KEY",
    },
    "openai": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "gemini": {
        "default_model": "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "anthropic": {
        "default_model": "claude-3-5-sonnet-20241022",
        "key_env": "ANTHROPIC_API_KEY",
    },
    "claude-code": {
        "default_model": None,
        "key_env": None,
    },
}


class LLMProvider:
    """Unified LLM provider interface."""

    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or settings.best_provider() or "deepseek"
        cfg = PROVIDER_CONFIGS.get(self.provider, {})
        self.model = model or settings.DEFAULT_MODEL or cfg.get("default_model", "")

    def call(self, messages: list[dict]) -> tuple[str, list, dict]:
        """Call provider with messages. Returns (content, tool_calls, raw_msg)."""
        cfg = PROVIDER_CONFIGS.get(self.provider, {})
        key_env = cfg.get("key_env")
        api_key = os.environ.get(key_env, "") if key_env else ""

        if self.provider in ("deepseek", "kimi", "openai"):
            return call_openai_compat(messages, cfg["api_url"], api_key, self.model)
        elif self.provider == "gemini":
            return call_gemini(messages, api_key, self.model)
        elif self.provider == "anthropic":
            return call_anthropic(messages, api_key, self.model)
        elif self.provider == "claude-code":
            return call_claude_code(messages)
        return "No provider configured.", [], {}

    def append_tool_results(
        self, messages: list[dict], raw_msg: dict, tool_calls: list, results: list[str]
    ) -> None:
        """Append tool results to messages in provider-specific format."""
        if self.provider == "gemini":
            messages.append({"role": "model", "parts": raw_msg.get("parts", [])})
            func_responses = [
                {"functionResponse": {
                    "name": tc.get("function", {}).get("name", ""),
                    "response": {"result": result},
                }}
                for tc, result in zip(tool_calls, results)
            ]
            messages.append({"role": "function", "parts": func_responses})
        elif self.provider == "anthropic":
            # Anthropic format
            tool_result_content = []
            for tc, result in zip(tool_calls, results):
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc.get("id", ""),
                    "content": result,
                })
            messages.append({"role": "user", "content": tool_result_content})
        else:
            # OpenAI-compatible
            import time
            assistant_msg = {"role": "assistant", "content": raw_msg.get("content", "")}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)
            for tc, result in zip(tool_calls, results):
                tc_id = tc.get("id", f"call_{int(time.time() * 1000)}")
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})
