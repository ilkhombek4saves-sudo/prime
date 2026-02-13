from __future__ import annotations

from pathlib import Path

from app.services.config_loader import ConfigLoader


def test_config_loader_expands_env_placeholders(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    providers = config_dir / "providers.yaml"
    providers.write_text(
        "\n".join(
            [
                "version: 1",
                "providers:",
                "  - name: openai_default",
                "    type: OpenAI",
                "    api_key: ${OPENAI_API_KEY}",
                "    api_base: ${OPENAI_BASE_URL:-https://api.openai.com/v1/}",
                "    models:",
                "      gpt-4o:",
                "        max_tokens: 4096",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    loader = ConfigLoader(base_path=str(config_dir))
    data = loader.load_yaml("providers.yaml")
    provider = data["providers"][0]
    assert provider["api_key"] == "sk-test-key"
    assert provider["api_base"] == "https://api.openai.com/v1/"


def test_config_loader_substitutes_empty_for_missing_env_without_default(
    tmp_path: Path,
    monkeypatch,
):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    bots = config_dir / "bots.yaml"
    bots.write_text(
        "\n".join(
            [
                "version: 1",
                "bots:",
                "  - name: support",
                "    token: ${MISSING_BOT_TOKEN}",
                "    channels: [telegram]",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_BOT_TOKEN", raising=False)

    loader = ConfigLoader(base_path=str(config_dir))
    data = loader.load_yaml("bots.yaml")
    assert data["bots"][0]["token"] == ""
