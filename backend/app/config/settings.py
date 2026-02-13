from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from typing import Literal


@dataclass
class Settings:
    app_name: str = "MultiBot Aggregator"
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./multibot.db"
    secret_key: str = "change-me"
    jwt_secret: str = "change-me-too"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_minutes: int = 60 * 24 * 14
    device_auth_ttl_seconds: int = 900
    device_auth_poll_interval_seconds: int = 3
    app_public_url: str = "http://localhost:8000"

    telegram_bot_tokens: str = ""

    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    anthropic_auth_token: str | None = None
    anthropic_base_url: str | None = None
    mistral_api_key: str | None = None
    deepseek_api_key: str | None = None
    qwen_api_key: str | None = None
    kimi_api_key: str | None = None
    zai_api_key: str | None = None

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    research_proxy_pool: str | None = None
    research_cache_ttl_seconds: int = 120
    research_http_timeout_seconds: float = 12.0
    research_max_retries: int = 3
    research_per_host_delay_ms: int = 450
    research_enrich_results: int = 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=getenv("APP_NAME", "MultiBot Aggregator"),
        app_env=getenv("APP_ENV", "dev"),
        app_host=getenv("APP_HOST", "0.0.0.0"),
        app_port=int(getenv("APP_PORT", "8000")),
        database_url=getenv("DATABASE_URL", "sqlite:///./multibot.db"),
        secret_key=getenv("SECRET_KEY", "change-me"),
        jwt_secret=getenv("JWT_SECRET", "change-me-too"),
        jwt_algorithm=getenv("JWT_ALGORITHM", "HS256"),
        access_token_ttl_minutes=int(getenv("ACCESS_TOKEN_TTL_MINUTES", "60")),
        refresh_token_ttl_minutes=int(getenv("REFRESH_TOKEN_TTL_MINUTES", str(60 * 24 * 14))),
        device_auth_ttl_seconds=int(getenv("DEVICE_AUTH_TTL_SECONDS", "900")),
        device_auth_poll_interval_seconds=int(getenv("DEVICE_AUTH_POLL_INTERVAL_SECONDS", "3")),
        app_public_url=getenv("APP_PUBLIC_URL", "http://localhost:8000"),
        telegram_bot_tokens=getenv("TELEGRAM_BOT_TOKENS", ""),
        openai_api_key=getenv("OPENAI_API_KEY"),
        gemini_api_key=getenv("GEMINI_API_KEY"),
        anthropic_auth_token=getenv("ANTHROPIC_AUTH_TOKEN"),
        anthropic_base_url=getenv("ANTHROPIC_BASE_URL"),
        mistral_api_key=getenv("MISTRAL_API_KEY"),
        deepseek_api_key=getenv("DEEPSEEK_API_KEY"),
        qwen_api_key=getenv("QWEN_API_KEY"),
        kimi_api_key=getenv("KIMI_API_KEY"),
        zai_api_key=getenv("ZAI_API_KEY"),
        s3_endpoint=getenv("S3_ENDPOINT"),
        s3_bucket=getenv("S3_BUCKET"),
        s3_access_key=getenv("S3_ACCESS_KEY"),
        s3_secret_key=getenv("S3_SECRET_KEY"),
        research_proxy_pool=getenv("RESEARCH_PROXY_POOL"),
        research_cache_ttl_seconds=int(getenv("RESEARCH_CACHE_TTL_SECONDS", "120")),
        research_http_timeout_seconds=float(getenv("RESEARCH_HTTP_TIMEOUT_SECONDS", "12")),
        research_max_retries=int(getenv("RESEARCH_MAX_RETRIES", "3")),
        research_per_host_delay_ms=int(getenv("RESEARCH_PER_HOST_DELAY_MS", "450")),
        research_enrich_results=int(getenv("RESEARCH_ENRICH_RESULTS", "2")),
    )
