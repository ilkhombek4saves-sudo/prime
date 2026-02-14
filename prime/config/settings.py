"""Configuration management — loads from .env files and environment"""
from __future__ import annotations

import os
from pathlib import Path


# ─── Paths ──────────────────────────────────────────────────────────────────
HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "prime"
CACHE_DIR = HOME / ".cache" / "prime"
DATA_DIR = HOME / ".prime"
MEMORY_DIR = DATA_DIR / "memory"
SKILLS_DIR = DATA_DIR / "skills"
DB_PATH = DATA_DIR / "prime.db"

# Create dirs on import
for d in [CONFIG_DIR, CACHE_DIR, DATA_DIR, MEMORY_DIR, SKILLS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ─── .env Loader ────────────────────────────────────────────────────────────
def load_env():
    """Load API keys from .env files (project root and ~/.config/prime/.env)"""
    project_root = Path(__file__).resolve().parent.parent.parent
    env_files = [
        project_root / ".env",
        CONFIG_DIR / ".env",
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


# ─── Settings ────────────────────────────────────────────────────────────────
class Settings:
    """Central settings — reads from environment variables."""

    # Telegram — @Chat_Geminibot
    TELEGRAM_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "6822269618:AAFXHD1c1_PtNJKK71SW-dHgwM1OFz4d_J8")
    TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "1267937858")

    # API providers
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    KIMI_API_KEY: str = os.environ.get("KIMI_API_KEY", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ZAI_API_KEY: str = os.environ.get("ZAI_API_KEY", "")

    # Gateway
    GATEWAY_HOST: str = os.environ.get("PRIME_GATEWAY_HOST", "0.0.0.0")
    GATEWAY_PORT: int = int(os.environ.get("PRIME_GATEWAY_PORT", "9000"))

    # Dashboard
    DASHBOARD_HOST: str = os.environ.get("PRIME_DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.environ.get("PRIME_DASHBOARD_PORT", "8080"))
    DASHBOARD_SECRET: str = os.environ.get("PRIME_DASHBOARD_SECRET", "prime-secret-key")

    # Agent
    WORKSPACE: str = os.environ.get("PRIME_WORKSPACE", str(Path.cwd()))
    MAX_TURNS: int = int(os.environ.get("PRIME_MAX_TURNS", "15"))
    DEFAULT_PROVIDER: str = os.environ.get("PRIME_PROVIDER", "")
    DEFAULT_MODEL: str = os.environ.get("PRIME_MODEL", "")

    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

    @classmethod
    def reload(cls):
        """Reload settings from environment (call after .env changes)."""
        load_env()
        cls.DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
        cls.KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
        cls.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
        cls.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        cls.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    @classmethod
    def available_providers(cls) -> list[str]:
        """Return list of providers with API keys configured."""
        providers = []
        if cls.DEEPSEEK_API_KEY:
            providers.append("deepseek")
        if cls.KIMI_API_KEY:
            providers.append("kimi")
        if cls.GEMINI_API_KEY:
            providers.append("gemini")
        if cls.OPENAI_API_KEY:
            providers.append("openai")
        if cls.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        return providers

    @classmethod
    def best_provider(cls) -> str | None:
        """Auto-select best available provider."""
        for p in cls.available_providers():
            return p
        return None


settings = Settings()
