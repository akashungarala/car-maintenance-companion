"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import health
from app.cache import RedisHealth, build_client
from app.database import Database
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.settings import Settings
from app.telemetry import configure_metrics, configure_tracing, instrument

logger = structlog.get_logger()


def create_app(
    *,
    settings: Settings | None = None,
    readiness: health.ReadinessRegistry | None = None,
) -> FastAPI:
    settings = settings or Settings()
    readiness = readiness or health.ReadinessRegistry(
        timeout_seconds=settings.readiness_timeout_seconds
    )
    configure_logging(settings)
    configure_tracing(settings)
    # Without a meter provider the FastAPI instrumentation records no metrics
    # at all: there is no RED data, and the service-health dashboard and the
    # error-rate and latency alerts have nothing to read.
    configure_metrics(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        # Nothing previously closed these. The process dying takes the sockets
        # with it, so it never showed in production -- but it leaks a
        # connection per app in the tests, and a graceful shutdown should hand
        # the database back its connections rather than have them time out.
        database = getattr(_app.state, "database", None)
        if database is not None:
            await database.dispose()
        cache = getattr(_app.state, "cache", None)
        if cache is not None:
            await cache.aclose()

    app = FastAPI(
        lifespan=lifespan,
        title="Car Maintenance Companion API",
        version=settings.version,
        root_path=settings.root_path,
        # Phase 0 exposes no product API. Docs stay on so the OpenAPI contract
        # pipeline (and its CI drift check) is wired before there is a contract.
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.readiness = readiness

    # Registered only when a database is configured, and only as *readiness*.
    # Liveness must never depend on it: a database blip would otherwise restart
    # every pod, turning a recoverable outage into a crash loop.
    if settings.database_url:
        database = Database(settings.database_url)
        app.state.database = database
        readiness.register("database", database.is_healthy)

    # Same reasoning as the database: readiness, never liveness. An instance
    # that cannot reach Redis cannot enqueue work or enforce a rate limit, so
    # it should leave the Service endpoints rather than half-serve requests.
    if settings.redis_url:
        cache = RedisHealth(build_client(settings.redis_url))
        app.state.cache = cache
        readiness.register("redis", cache.is_healthy)

    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)

    # After the routes exist, so instrumentation sees them; excluded_urls keeps
    # the probes out of traces.
    instrument(app, engine=getattr(app.state, "database", None) and app.state.database._engine)

    logger.info(
        "application_started",
        environment=settings.environment,
        readiness_checks=list(readiness.names),
    )
    return app
