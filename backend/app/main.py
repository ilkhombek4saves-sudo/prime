import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config.settings import get_settings
from app.logging.setup import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.proxy_trust import TrustedProxyMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.monitoring.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.persistence.migrations import run_migrations
from app.services.config_sync import sync_config_to_db
from app.services.config_watch import ConfigWatcher
from os import getenv

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate config files at boot — fail fast on schema errors
    try:
        from app.services.config_loader import ConfigLoader

        ConfigLoader().load_and_validate()
    except Exception as exc:  # pragma: no cover
        logger.error("Config validation error: %s", exc, exc_info=True)

    # Apply DB migrations (non-fatal)
    try:
        run_migrations()
    except Exception as exc:  # pragma: no cover
        logger.error("DB migration failed — running in degraded mode: %s", exc, exc_info=True)

    # Sync config to DB (best-effort)
    try:
        sync_config_to_db()
    except Exception as exc:  # pragma: no cover
        logger.error("Config sync failed: %s", exc, exc_info=True)

    # Acquire gateway lock (single instance safety)
    lock_file = None
    settings = get_settings()
    try:
        from pathlib import Path

        lock_path = Path(settings.gateway_lock_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = lock_path.open("w")
        try:
            import fcntl  # type: ignore

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as exc:
            raise RuntimeError(f"Gateway lock already held: {lock_path}") from exc
    except Exception as exc:  # pragma: no cover
        logger.error("Gateway lock failed: %s", exc, exc_info=True)

    # Start background worker (task execution + document indexing)
    worker = None
    try:
        from app.services.worker import get_worker

        worker = get_worker()
        await worker.start()
    except Exception as exc:  # pragma: no cover
        logger.error("Background worker failed to start: %s", exc, exc_info=True)

    # Start Telegram gateway if tokens are configured
    tg_gateway = None
    settings = get_settings()
    if settings.telegram_bot_tokens.strip():
        try:
            from app.gateway.telegram import build_telegram_gateway

            tg_gateway = build_telegram_gateway(settings.telegram_bot_tokens)
            await tg_gateway.start()
            logger.info("Telegram gateway started")
        except Exception as exc:  # pragma: no cover
            logger.error("Telegram gateway failed to start: %s", exc, exc_info=True)

    # Start Discord gateway if configured
    discord_gateway = None
    discord_configs_raw = getenv("DISCORD_BOT_CONFIGS", "").strip()
    if discord_configs_raw:
        try:
            import json as _json
            from app.gateway.discord import build_discord_gateway
            discord_configs = _json.loads(discord_configs_raw)
            discord_gateway = build_discord_gateway(discord_configs)
            await discord_gateway.start()
            logger.info("Discord gateway started")
        except Exception as exc:
            logger.error("Discord gateway failed to start: %s", exc, exc_info=True)

    # Start Slack gateway if configured
    slack_gateway = None
    if getenv("SLACK_BOT_TOKEN", "").strip():
        try:
            from app.gateway.slack import build_slack_gateway
            slack_gateway = build_slack_gateway()
            if slack_gateway:
                await slack_gateway.start()
                logger.info("Slack gateway started")
        except Exception as exc:
            logger.error("Slack gateway failed to start: %s", exc, exc_info=True)

    # Start WhatsApp gateway if configured
    whatsapp_gateway = None
    if getenv("WHATSAPP_TOKEN", "").strip() and getenv("WHATSAPP_PHONE_ID", "").strip():
        try:
            from app.gateway.whatsapp import build_whatsapp_gateway
            whatsapp_gateway = build_whatsapp_gateway()
            if whatsapp_gateway:
                await whatsapp_gateway.start()
                logger.info("WhatsApp gateway started")
        except Exception as exc:
            logger.error("WhatsApp gateway failed to start: %s", exc, exc_info=True)

    # Config hot-reload
    config_watcher = None
    if settings.config_watch_enabled:
        try:
            config_watcher = ConfigWatcher(interval_seconds=settings.config_watch_interval_seconds)
            await config_watcher.start()
            logger.info("Config watcher started")
        except Exception as exc:  # pragma: no cover
            logger.error("Config watcher failed to start: %s", exc, exc_info=True)

    # Register bundled skills
    try:
        from app.skills.registry import SkillsRegistry
        SkillsRegistry.register_bundled()
        logger.info("Bundled skills registered")
    except Exception as exc:  # pragma: no cover
        logger.error("Skills registry failed: %s", exc, exc_info=True)

    # Start cron scheduler
    try:
        from app.services.cron_service import CronService
        await CronService.start()
        logger.info("Cron scheduler started")
    except Exception as exc:  # pragma: no cover
        logger.error("Cron service failed to start: %s", exc, exc_info=True)

    # Start browser bridge (best-effort)
    try:
        from app.services.browser_service import BrowserService
        BrowserService.ensure_running()
        logger.info("Browser bridge checked")
    except Exception as exc:  # pragma: no cover
        logger.debug("Browser bridge not started: %s", exc)

    yield

    # Stop cron scheduler
    try:
        from app.services.cron_service import CronService
        await CronService.stop()
    except Exception as exc:  # pragma: no cover
        logger.warning("Cron service stop error: %s", exc)

    # Stop browser bridge
    try:
        from app.services.browser_service import BrowserService
        BrowserService.stop()
    except Exception as exc:  # pragma: no cover
        logger.warning("Browser bridge stop error: %s", exc)

    if config_watcher is not None:
        try:
            await config_watcher.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("Config watcher stop error: %s", exc)

    if discord_gateway is not None:
        try:
            await discord_gateway.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("Discord gateway stop error: %s", exc)

    if slack_gateway is not None:
        try:
            await slack_gateway.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("Slack gateway stop error: %s", exc)

    if whatsapp_gateway is not None:
        try:
            await whatsapp_gateway.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("WhatsApp gateway stop error: %s", exc)

    if tg_gateway is not None:
        try:
            await tg_gateway.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("Telegram gateway stop error: %s", exc)

    if worker is not None:
        try:
            await worker.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning("Worker stop error: %s", exc)

    if lock_file is not None:
        try:
            lock_file.close()
        except Exception:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # CORS — allow frontend origins (restrict in production via CORS_ORIGINS env var)
    cors_env = getenv("CORS_ORIGINS", "").strip()
    if cors_env:
        allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:80",
            "http://localhost",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedProxyMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - start
        path = request.url.path
        method = request.method
        REQUEST_COUNT.labels(path=path, method=method, status=response.status_code).inc()
        REQUEST_LATENCY.labels(path=path, method=method).observe(elapsed)
        return response

    app.include_router(api_router)

    # Mount public webhook receiver at root (not under /api)
    from app.api.webhooks import public_router as webhook_public_router
    app.include_router(webhook_public_router)

    # Mount WhatsApp webhook at root (Meta requires non-/api path)
    from app.gateway.whatsapp import webhook_router as whatsapp_webhook_router
    app.include_router(whatsapp_webhook_router)

    # Mount Slack HTTP Events endpoint at root (for non-Socket-Mode deployments)
    from fastapi import Request as _Request
    from fastapi.responses import JSONResponse as _JSONResponse

    @app.post("/slack/events", tags=["slack"])
    async def slack_events_http(request: _Request):
        """Receive Slack Events API callbacks (HTTP mode, no app token)."""
        from app.gateway.slack import _gateway_instance as _slack_gw
        if _slack_gw is None:
            return _JSONResponse({"error": "slack_not_configured"}, status_code=503)
        body = await request.body()
        headers = dict(request.headers)
        result = await _slack_gw.handle_http_event(body, headers)
        return result

    return app


app = create_app()
