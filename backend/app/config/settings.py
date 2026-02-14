import logging
import secrets
from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from typing import Literal

logger = logging.getLogger(__name__)

_INSECURE_DEFAULTS = {"change-me", "change-me-too", ""}


@dataclass
class Settings:
    app_name: str = "MultiBot Aggregator"
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_version: str = "0.1.0"
    app_commit: str | None = None
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./multibot.db"
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_minutes: int = 60 * 24 * 14
    device_auth_ttl_seconds: int = 900
    device_auth_poll_interval_seconds: int = 3
    app_public_url: str = "http://localhost:8000"

    telegram_bot_tokens: str = ""
    discord_bot_configs: str = ""
    webchat_enabled: bool = True

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
    telegram_show_errors: bool = False
    ws_protocol_min: int = 3
    ws_protocol_max: int = 3
    ws_strict_connect: bool = True
    ws_max_payload_bytes: int = 2_000_000
    ws_max_buffered_bytes: int = 8_000_000
    ws_tick_interval_ms: int = 20_000
    ws_allow_remote: bool = False
    trusted_proxy_cidrs: str | None = None
    allow_forwarded_headers: bool = False
    gateway_password: str | None = None
    gateway_lock_path: str = "/tmp/prime-gateway.lock"
    config_watch_enabled: bool = True
    config_watch_interval_seconds: float = 3.0
    config_reload_mode: Literal["hot", "hybrid", "off"] = "hot"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    def _as_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    app_env = getenv("APP_ENV", "dev")

    secret_key = getenv("SECRET_KEY", "")
    jwt_secret = getenv("JWT_SECRET", "")

    # In production, refuse to start with insecure/missing secrets
    if app_env == "prod":
        if secret_key in _INSECURE_DEFAULTS:
            raise RuntimeError(
                "SECRET_KEY is not set or uses an insecure default. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if jwt_secret in _INSECURE_DEFAULTS:
            raise RuntimeError(
                "JWT_SECRET is not set or uses an insecure default. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
    else:
        # In dev/test, generate random secrets if not provided
        if secret_key in _INSECURE_DEFAULTS:
            secret_key = secrets.token_hex(32)
            logger.warning("SECRET_KEY not set — using auto-generated value (not suitable for production)")
        if jwt_secret in _INSECURE_DEFAULTS:
            jwt_secret = secrets.token_hex(32)
            logger.warning("JWT_SECRET not set — using auto-generated value (not suitable for production)")

    return Settings(
        app_name=getenv("APP_NAME", "MultiBot Aggregator"),
        app_env=app_env,
        app_version=getenv("APP_VERSION", "0.1.0"),
        app_commit=getenv("APP_COMMIT"),
        app_host=getenv("APP_HOST", "0.0.0.0"),
        app_port=int(getenv("APP_PORT", "8000")),
        database_url=getenv("DATABASE_URL", "sqlite:///./multibot.db"),
        secret_key=secret_key,
        jwt_secret=jwt_secret,
        jwt_algorithm=getenv("JWT_ALGORITHM", "HS256"),
        access_token_ttl_minutes=int(getenv("ACCESS_TOKEN_TTL_MINUTES", "60")),
        refresh_token_ttl_minutes=int(getenv("REFRESH_TOKEN_TTL_MINUTES", str(60 * 24 * 14))),
        device_auth_ttl_seconds=int(getenv("DEVICE_AUTH_TTL_SECONDS", "900")),
        device_auth_poll_interval_seconds=int(getenv("DEVICE_AUTH_POLL_INTERVAL_SECONDS", "3")),
        app_public_url=getenv("APP_PUBLIC_URL", "http://localhost:8000"),
        telegram_bot_tokens=getenv("TELEGRAM_BOT_TOKENS", ""),
        discord_bot_configs=getenv("DISCORD_BOT_CONFIGS", ""),
        webchat_enabled=_as_bool(getenv("WEBCHAT_ENABLED"), True),
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
        telegram_show_errors=_as_bool(getenv("TELEGRAM_SHOW_ERRORS"), False),
        ws_protocol_min=int(getenv("WS_PROTOCOL_MIN", "3")),
        ws_protocol_max=int(getenv("WS_PROTOCOL_MAX", "3")),
        ws_strict_connect=_as_bool(getenv("WS_STRICT_CONNECT"), True),
        ws_max_payload_bytes=int(getenv("WS_MAX_PAYLOAD_BYTES", "2000000")),
        ws_max_buffered_bytes=int(getenv("WS_MAX_BUFFERED_BYTES", "8000000")),
        ws_tick_interval_ms=int(getenv("WS_TICK_INTERVAL_MS", "20000")),
        ws_allow_remote=_as_bool(getenv("WS_ALLOW_REMOTE"), False),
        trusted_proxy_cidrs=getenv("TRUSTED_PROXY_CIDRS"),
        allow_forwarded_headers=_as_bool(getenv("ALLOW_FORWARDED_HEADERS"), False),
        gateway_password=getenv("GATEWAY_PASSWORD"),
        gateway_lock_path=getenv("GATEWAY_LOCK_PATH", "/tmp/prime-gateway.lock"),
        config_watch_enabled=_as_bool(getenv("CONFIG_WATCH_ENABLED"), True),
        config_watch_interval_seconds=float(getenv("CONFIG_WATCH_INTERVAL_SECONDS", "3")),
        config_reload_mode=getenv("CONFIG_RELOAD_MODE", "hot"),
    )
