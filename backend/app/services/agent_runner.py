"""
AgentRunner — iterative tool-calling loop.

Supports two provider families:
  - OpenAI-compatible  (finish_reason == "tool_calls", role="tool" follow-ups)
  - Anthropic          (stop_reason == "tool_use", tool_result content blocks)

The runner calls the provider, inspects the response for tool calls, executes
them via WorkspaceService, injects results, and loops until the model produces
a plain-text response or MAX_TURNS is reached.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.providers.base import ProviderError
from app.services.tools import TOOLS_ANTHROPIC, TOOLS_OPENAI, execute_tool
from app.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)

MAX_TURNS = 12


@dataclass
class AgentRunResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class AgentRunner:
    """Stateless runner — instantiate once and call run() per message."""

    def run(
        self,
        user_message: str,
        *,
        provider_type: Any,
        provider_name: str,
        provider_config: dict[str, Any],
        system: str | None = None,
        history: list[dict] | None = None,
        workspace_path: str | None = None,
        on_token: Callable[[str], None] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        parent_session_id: str | None = None,
    ) -> str:
        """
        Backward-compatible wrapper that returns only the plain text response.
        Use run_with_meta() to get usage and selected model.
        """
        result = self.run_with_meta(
            user_message,
            provider_type=provider_type,
            provider_name=provider_name,
            provider_config=provider_config,
            system=system,
            history=history,
            workspace_path=workspace_path,
            on_token=on_token,
            model=model,
            max_tokens=max_tokens,
            session_id=session_id,
            agent_id=agent_id,
            parent_session_id=parent_session_id,
        )
        return result.text

    def run_with_meta(
        self,
        user_message: str,
        *,
        provider_type: Any,
        provider_name: str,
        provider_config: dict[str, Any],
        system: str | None = None,
        history: list[dict] | None = None,
        workspace_path: str | None = None,
        on_token: Callable[[str], None] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        parent_session_id: str | None = None,
    ) -> AgentRunResult:
        """
        Run the agentic loop and return text + usage metadata.

        If workspace_path is None tools are disabled — falls back to a plain chat.
        """
        history = list(history or [])
        workspace = (
            WorkspaceService(
                workspace_path,
                humanization=provider_config.get("humanization"),
            )
            if workspace_path
            else None
        )
        use_tools = workspace is not None

        provider_kind = self._normalize_provider_type(provider_type)
        if provider_kind == "Anthropic":
            return self._run_anthropic(
                user_message,
                system=system,
                history=history,
                config=provider_config,
                workspace=workspace,
                use_tools=use_tools,
                on_token=on_token,
                model_override=model,
                max_tokens_override=max_tokens,
                session_id=session_id,
                agent_id=agent_id,
            )
        # All OpenAI-compatible providers
        return self._run_openai(
            user_message,
            system=system,
            history=history,
            config=provider_config,
            workspace=workspace,
            use_tools=use_tools,
            on_token=on_token,
            model_override=model,
            max_tokens_override=max_tokens,
            session_id=session_id,
            agent_id=agent_id,
        )

    @staticmethod
    def _normalize_provider_type(provider_type: Any) -> str:
        if hasattr(provider_type, "value"):
            return str(provider_type.value)
        raw = str(provider_type)
        if raw.startswith("ProviderType."):
            return raw.split(".", 1)[1]
        return raw

    @staticmethod
    def _estimate_tokens(text: str | None) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    # ── OpenAI-compatible ──────────────────────────────────────────────────────

    def _run_openai(
        self,
        user_message: str,
        *,
        system: str | None,
        history: list[dict],
        config: dict[str, Any],
        workspace: WorkspaceService | None,
        use_tools: bool,
        on_token: Callable[[str], None] | None,
        model_override: str | None,
        max_tokens_override: int | None,
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> AgentRunResult:
        api_key = config.get("api_key", "")
        base_url = config.get("api_base", "https://api.openai.com/v1").rstrip("/")
        model = model_override or config.get("default_model", "gpt-4o")
        model_cfg = (config.get("models") or {}).get(model, {})
        max_tokens = int(max_tokens_override or model_cfg.get("max_tokens", 4096))

        headers = {"Content-Type": "application/json"}
        # Local/OpenAI-compatible providers (e.g. Ollama) may not require auth at all.
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Build initial messages
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        base_input_estimate = (
            self._estimate_tokens(system)
            + sum(self._estimate_tokens(item.get("content")) for item in history)
            + self._estimate_tokens(user_message)
        )

        # Stream only for plain chat mode. Tool-calling responses need a full structured payload.
        if on_token and not use_tools:
            text, usage = self._run_openai_stream(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                headers=headers,
                base_url=base_url,
                on_token=on_token,
            )
            input_tokens = usage.get("input_tokens", 0) or base_input_estimate
            output_tokens = usage.get("output_tokens", 0) or self._estimate_tokens(text)
            return AgentRunResult(
                text=text,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        input_tokens_total = 0
        output_tokens_total = 0

        for _ in range(MAX_TURNS):
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if use_tools:
                payload["tools"] = TOOLS_OPENAI
                payload["tool_choice"] = "auto"

            try:
                with httpx.Client(timeout=120) as client:
                    resp = client.post(
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    f"OpenAI API {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(f"OpenAI request failed: {exc}") from exc

            usage = data.get("usage") or {}
            input_tokens_total += int(usage.get("prompt_tokens") or 0)
            output_tokens_total += int(usage.get("completion_tokens") or 0)

            choice = data["choices"][0]
            finish = choice.get("finish_reason", "")
            assistant_msg = choice["message"]

            if finish != "tool_calls" or not assistant_msg.get("tool_calls"):
                text = assistant_msg.get("content") or ""
                if input_tokens_total <= 0:
                    input_tokens_total = base_input_estimate
                if output_tokens_total <= 0:
                    output_tokens_total = self._estimate_tokens(text)
                return AgentRunResult(
                    text=text,
                    model=model,
                    input_tokens=input_tokens_total,
                    output_tokens=output_tokens_total,
                )

            # ── Execute tool calls ────────────────────────────────────────────
            messages.append(assistant_msg)  # add assistant tool_calls message

            for tc in assistant_msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                result = execute_tool(
                    name, args, workspace,
                    session_id=session_id,
                    agent_id=agent_id,
                )
                logger.info("Tool %s(%s) → %s", name, list(args.keys()), result[:80])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        text = "Reached maximum tool-use iterations."
        if input_tokens_total <= 0:
            input_tokens_total = base_input_estimate
        if output_tokens_total <= 0:
            output_tokens_total = self._estimate_tokens(text)
        return AgentRunResult(
            text=text,
            model=model,
            input_tokens=input_tokens_total,
            output_tokens=output_tokens_total,
        )

    def _run_openai_stream(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        headers: dict[str, str],
        base_url: str,
        on_token: Callable[[str], None],
    ) -> tuple[str, dict[str, int]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        text_parts: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        error_body = response.read()
                        error_text = (
                            error_body.decode("utf-8", errors="ignore")
                            if isinstance(error_body, bytes)
                            else str(error_body)
                        )
                        raise ProviderError(
                            f"OpenAI API {response.status_code}: {error_text}"
                        )
                    for raw_line in response.iter_lines():
                        if not raw_line:
                            continue
                        line = (
                            raw_line.decode("utf-8", errors="ignore")
                            if isinstance(raw_line, bytes)
                            else raw_line
                        )
                        if not line.startswith("data:"):
                            continue
                        data_raw = line[5:].strip()
                        if data_raw == "[DONE]":
                            break
                        try:
                            event = json.loads(data_raw)
                        except json.JSONDecodeError:
                            continue

                        choice = (event.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        token = delta.get("content")
                        if token:
                            text_parts.append(token)
                            try:
                                on_token(token)
                            except Exception:
                                pass
                        usage_event = event.get("usage")
                        if isinstance(usage_event, dict):
                            usage["input_tokens"] = int(
                                usage_event.get("prompt_tokens") or usage["input_tokens"]
                            )
                            usage["output_tokens"] = int(
                                usage_event.get("completion_tokens") or usage["output_tokens"]
                            )
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"OpenAI API {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        return "".join(text_parts), usage

    # ── Anthropic ──────────────────────────────────────────────────────────────

    def _run_anthropic(
        self,
        user_message: str,
        *,
        system: str | None,
        history: list[dict],
        config: dict[str, Any],
        workspace: WorkspaceService | None,
        use_tools: bool,
        on_token: Callable[[str], None] | None,
        model_override: str | None,
        max_tokens_override: int | None,
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> AgentRunResult:
        api_key = config.get("api_key", "")
        base_url = config.get("api_base", "https://api.anthropic.com").rstrip("/")
        model = model_override or config.get("default_model", "claude-sonnet-4-5-20250929")
        model_cfg = (config.get("models") or {}).get(model, {})
        max_tokens = int(max_tokens_override or model_cfg.get("max_tokens", 4096))

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        messages: list[dict] = list(history) + [{"role": "user", "content": user_message}]
        base_input_estimate = (
            self._estimate_tokens(system)
            + sum(self._estimate_tokens(item.get("content")) for item in history)
            + self._estimate_tokens(user_message)
        )

        # Stream only for plain chat mode. Tool-calling responses need full content blocks.
        if on_token and not use_tools:
            text, usage = self._run_anthropic_stream(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                system=system,
                headers=headers,
                base_url=base_url,
                on_token=on_token,
            )
            input_tokens = usage.get("input_tokens", 0) or base_input_estimate
            output_tokens = usage.get("output_tokens", 0) or self._estimate_tokens(text)
            return AgentRunResult(
                text=text,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        input_tokens_total = 0
        output_tokens_total = 0

        for _ in range(MAX_TURNS):
            payload: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                payload["system"] = system
            if use_tools:
                payload["tools"] = TOOLS_ANTHROPIC

            try:
                with httpx.Client(timeout=120) as client:
                    resp = client.post(
                        f"{base_url}/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    f"Anthropic API {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(f"Anthropic request failed: {exc}") from exc

            usage = data.get("usage") or {}
            input_tokens_total += int(
                usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            )
            output_tokens_total += int(
                usage.get("output_tokens") or usage.get("completion_tokens") or 0
            )

            stop_reason = data.get("stop_reason", "")
            content_blocks = data.get("content", [])

            tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
            text_blocks = [b for b in content_blocks if b.get("type") == "text"]

            if stop_reason != "tool_use" or not tool_use_blocks:
                text = text_blocks[0]["text"] if text_blocks else ""
                if input_tokens_total <= 0:
                    input_tokens_total = base_input_estimate
                if output_tokens_total <= 0:
                    output_tokens_total = self._estimate_tokens(text)
                return AgentRunResult(
                    text=text,
                    model=model,
                    input_tokens=input_tokens_total,
                    output_tokens=output_tokens_total,
                )

            # ── Execute tool calls ────────────────────────────────────────────
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results = []
            for block in tool_use_blocks:
                name = block["name"]
                args = block.get("input", {})
                result = execute_tool(
                    name, args, workspace,
                    session_id=session_id,
                    agent_id=agent_id,
                )
                logger.info("Tool %s(%s) → %s", name, list(args.keys()), result[:80])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        text = "Reached maximum tool-use iterations."
        if input_tokens_total <= 0:
            input_tokens_total = base_input_estimate
        if output_tokens_total <= 0:
            output_tokens_total = self._estimate_tokens(text)
        return AgentRunResult(
            text=text,
            model=model,
            input_tokens=input_tokens_total,
            output_tokens=output_tokens_total,
        )

    def _run_anthropic_stream(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str | None,
        headers: dict[str, str],
        base_url: str,
        on_token: Callable[[str], None],
    ) -> tuple[str, dict[str, int]]:
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system

        text_parts: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/v1/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    for raw_line in response.iter_lines():
                        if not raw_line:
                            continue
                        line = (
                            raw_line.decode("utf-8", errors="ignore")
                            if isinstance(raw_line, bytes)
                            else raw_line
                        )
                        if not line.startswith("data:"):
                            continue
                        data_raw = line[5:].strip()
                        if not data_raw or data_raw == "[DONE]":
                            continue
                        try:
                            event = json.loads(data_raw)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")
                        if event_type == "message_start":
                            usage_event = (event.get("message") or {}).get("usage") or {}
                            usage["input_tokens"] = int(
                                usage_event.get("input_tokens") or usage["input_tokens"]
                            )
                            usage["output_tokens"] = int(
                                usage_event.get("output_tokens") or usage["output_tokens"]
                            )
                        elif event_type == "message_delta":
                            usage_event = event.get("usage") or {}
                            usage["input_tokens"] = int(
                                usage_event.get("input_tokens") or usage["input_tokens"]
                            )
                            usage["output_tokens"] = int(
                                usage_event.get("output_tokens") or usage["output_tokens"]
                            )

                        if event.get("type") != "content_block_delta":
                            continue
                        token = (event.get("delta") or {}).get("text", "")
                        if token:
                            text_parts.append(token)
                            try:
                                on_token(token)
                            except Exception:
                                pass
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Anthropic API {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        return "".join(text_parts), usage
