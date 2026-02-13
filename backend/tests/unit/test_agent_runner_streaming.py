from __future__ import annotations

from app.persistence.models import ProviderType
from app.services.agent_runner import AgentRunner


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        return iter(self._lines)


class _FakeClientBase:
    lines: list[str] = []

    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.last_payload = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def stream(self, method, url, headers=None, json=None):  # noqa: ANN001
        self.last_payload = json
        return _FakeStreamResponse(self.lines)


def test_agent_runner_streams_openai(monkeypatch):
    class FakeOpenAIClient(_FakeClientBase):
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]

    monkeypatch.setattr("app.services.agent_runner.httpx.Client", FakeOpenAIClient)

    tokens: list[str] = []
    runner = AgentRunner()
    result = runner.run(
        "hi",
        provider_type="OpenAI",
        provider_name="openai_default",
        provider_config={
            "api_key": "x",
            "api_base": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "models": {"gpt-4o": {"max_tokens": 100}},
        },
        on_token=tokens.append,
    )
    assert result == "Hello world"
    assert tokens == ["Hello", " world"]


def test_agent_runner_streams_anthropic(monkeypatch):
    class FakeAnthropicClient(_FakeClientBase):
        lines = [
            'data: {"type":"content_block_delta","delta":{"text":"Hi"}}',
            'data: {"type":"content_block_delta","delta":{"text":" there"}}',
            "data: [DONE]",
        ]

    monkeypatch.setattr("app.services.agent_runner.httpx.Client", FakeAnthropicClient)

    tokens: list[str] = []
    runner = AgentRunner()
    result = runner.run(
        "hi",
        provider_type=ProviderType.Anthropic,
        provider_name="anthropic_default",
        provider_config={
            "api_key": "x",
            "api_base": "https://api.anthropic.com",
            "default_model": "claude-3-5-sonnet-20241022",
            "models": {"claude-3-5-sonnet-20241022": {"max_tokens": 100}},
        },
        on_token=tokens.append,
    )
    assert result == "Hi there"
    assert tokens == ["Hi", " there"]


def test_agent_runner_run_with_meta_collects_stream_usage(monkeypatch):
    class FakeOpenAIClient(_FakeClientBase):
        lines = [
            'data: {"choices":[{"delta":{"content":"A"}}]}',
            'data: {"choices":[{"delta":{"content":"B"}}]}',
            'data: {"usage":{"prompt_tokens":11,"completion_tokens":7}}',
            "data: [DONE]",
        ]

    monkeypatch.setattr("app.services.agent_runner.httpx.Client", FakeOpenAIClient)

    runner = AgentRunner()
    result = runner.run_with_meta(
        "hi",
        provider_type=ProviderType.OpenAI,
        provider_name="openai_default",
        provider_config={
            "api_key": "x",
            "api_base": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "models": {"gpt-4o": {"max_tokens": 100}},
        },
        on_token=lambda _token: None,
    )
    assert result.text == "AB"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
