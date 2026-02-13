from __future__ import annotations

import stat
from pathlib import Path

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.http_provider import HTTPProvider
from app.providers.shell_provider import ShellProvider


def test_shell_provider_runs_allowlisted_script(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script = scripts_dir / "deploy.sh"
    script.write_text("#!/usr/bin/env bash\necho ok-$1\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    provider = ShellProvider(
        name="shell",
        config={
            "allowed_scripts": ["deploy.sh"],
            "scripts_dir": str(scripts_dir),
            "humanization": {
                "enabled": True,
                "think_delay_min_ms": 0,
                "think_delay_max_ms": 0,
                "max_total_delay_ms": 0,
            },
        },
    )
    provider.validate_config()
    result = provider.run_cli("deploy.sh service-a")
    assert result["returncode"] == 0
    assert "ok-service-a" in result["stdout"]
    assert result["humanization"]["enabled"] is True


def test_shell_provider_blocks_non_allowlisted_script():
    provider = ShellProvider(name="shell", config={"allowed_scripts": ["deploy.sh"]})
    provider.validate_config()
    with pytest.raises(ProviderError):
        provider.run_cli("backup.sh")


def test_http_provider_rejects_absolute_url_without_flag():
    provider = HTTPProvider(name="http", config={"base_url": "https://api.example.com"})
    provider.validate_config()
    with pytest.raises(ProviderError):
        provider.run_api_call({"method": "GET", "url": "https://evil.example.com/ping"})


def test_http_provider_joins_base_url_and_returns_payload(monkeypatch):
    captured: dict[str, str] = {}

    def fake_request(self, method, url, headers=None, json=None):  # noqa: ANN001
        captured["method"] = method
        captured["url"] = url
        req = httpx.Request(method, url)
        return httpx.Response(200, request=req, json={"ok": True, "echo": json})

    monkeypatch.setattr(httpx.Client, "request", fake_request)

    provider = HTTPProvider(
        name="http",
        config={
            "base_url": "https://api.example.com/v1",
            "default_headers": {"x-service": "owncli"},
        },
    )
    provider.validate_config()

    result = provider.run_api_call(
        {"method": "POST", "url": "/ping", "body": {"hello": "world"}, "headers": {"x-req": "1"}}
    )
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.example.com/v1/ping"
    assert result["status_code"] == 200
    assert result["payload"]["ok"] is True
