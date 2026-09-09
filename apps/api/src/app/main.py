"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import health
from app.cache import RedisHealth, build_client
from app.database import Database
from app.garage.router import router as garage_router
from app.identity.router import router as auth_router
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.rate_limit import RateLimiter
from app.rate_limit_middleware import RateLimitMiddleware
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
        # The ARQ pool is built here rather than in create_app because it is
        # async, and because a pool created at import time outlives reloads in
        # development and leaks connections.
        if settings.redis_url:
            from arq import create_pool

            from app.queue import build_redis_settings

            _app.state.queue = await create_pool(build_redis_settings(settings.redis_url))
        yield
        queue = getattr(_app.state, "queue", None)
        if queue is not None:
            await queue.aclose()
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
        client = build_client(settings.redis_url)
        cache = RedisHealth(client)
        app.state.cache = cache
        readiness.register("redis", cache.is_healthy)
        # Added before RequestContextMiddleware below, which means Starlette
        # runs it *after* -- middleware is applied in reverse. That ordering is
        # deliberate: a refused request should still get a request id and an
        # access log line, or 429s become invisible in the logs.
        app.add_middleware(RateLimitMiddleware, limiter=RateLimiter(client), settings=settings)

    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    # Only when there is somewhere to store tokens and something to enqueue
    # with. Mounting it regardless would give a 500 where a missing route is
    # both more honest and easier to diagnose.
    if settings.database_url and settings.redis_url:
        app.include_router(auth_router)
        app.include_router(garage_router)

    # After the routes exist, so instrumentation sees them; excluded_urls keeps
    # the probes out of traces.
    instrument(app, engine=getattr(app.state, "database", None) and app.state.database._engine)

    logger.info(
        "application_started",
        environment=settings.environment,
        readiness_checks=list(readiness.names),
    )
    return app
