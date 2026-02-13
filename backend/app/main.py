import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config.settings import get_settings
from app.logging.setup import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.monitoring.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.persistence.migrations import run_migrations

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

    yield

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


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # CORS — allow frontend origins (restrict in production via env var)
    allowed_origins = [
        "http://localhost:3000",   # landing page
        "http://localhost:5173",   # admin dashboard (dev)
        "http://localhost:80",
        "http://localhost",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestContextMiddleware)
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
    return app


app = create_app()
