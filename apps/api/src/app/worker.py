"""ARQ worker entrypoint: `arq app.worker.WorkerSettings`.

Separate from the API process on purpose (ADR-0005). The worker runs long
projection and digest jobs whose failure modes and scaling curve differ from
request handling, and which must never occupy a request-handling process.
"""

from collections.abc import Callable
from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from app.logging import configure_logging
from app.queue import build_redis_settings
from app.settings import Settings
from app.tasks import heartbeat, with_dead_letter

logger = structlog.get_logger()

# Three attempts, then the dead-letter list. More retries on a job that is
# genuinely broken only delays the alert.
MAX_TRIES = 3


def _redis_settings() -> RedisSettings:
    """Resolve Redis settings without raising at import time.

    ARQ reads this off the class, so raising here would make the module
    unimportable whenever the variable is unset — including during test
    collection. Misconfiguration is caught in `startup` instead, which fails
    loudly at the point it actually matters.
    """
    url = Settings().redis_url
    return build_redis_settings(url) if url else RedisSettings()


async def startup(ctx: dict[str, Any]) -> None:
    settings = Settings()
    configure_logging(settings)
    if not settings.redis_url:
        raise RuntimeError(
            "CMC_REDIS_URL is not set. The worker would connect to localhost and "
            "idle forever consuming nothing, which looks like a quiet queue "
            "rather than a broken deployment."
        )
    logger.info("worker_started", max_tries=MAX_TRIES)


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_stopping")


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Any]]] = [
        with_dead_letter(heartbeat, max_tries=MAX_TRIES)
    ]
    redis_settings: ClassVar[RedisSettings] = _redis_settings()
    on_startup: ClassVar[Any] = startup
    on_shutdown: ClassVar[Any] = shutdown
    max_tries: ClassVar[int] = MAX_TRIES
    # Bounded so a hung job cannot occupy the worker indefinitely, with the
    # CronJob piling work up behind it.
    job_timeout: ClassVar[int] = 120
    # One job at a time: this shares two CPUs with the API and the database, so
    # concurrency here is taken directly from request handling.
    max_jobs: ClassVar[int] = 1
    keep_result: ClassVar[int] = 3600
