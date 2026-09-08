"""Application factory."""

import structlog
from fastapi import FastAPI

from app import health
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.settings import Settings

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

    app = FastAPI(
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

    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)

    logger.info(
        "application_started",
        environment=settings.environment,
        readiness_checks=list(readiness.names),
    )
    return app
