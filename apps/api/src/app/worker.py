"""ARQ worker entrypoint: `arq app.worker.WorkerSettings`.

Separate from the API process on purpose (ADR-0005). The worker runs long
projection and digest jobs whose failure modes and scaling curve differ from
request handling, and which must never occupy a request-handling process.
"""

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from app import metrics as job_metrics
from app.logging import configure_logging
from app.queue import build_redis_settings, queue_depth
from app.settings import Settings
from app.tasks import heartbeat, with_dead_letter
from app.telemetry import (
    configure_metrics,
    configure_tracing,
    flush_metrics,
    flush_tracing,
    instrument,
)

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


# Often enough that the series never goes stale, rarely enough to be free.
QUEUE_DEPTH_INTERVAL_SECONDS = 30.0


async def record_queue_depth_once(redis: Any) -> None:
    """Sample the queue once.

    Errors are swallowed deliberately. An unhandled exception here would end
    the polling task silently, and queue depth would stop being reported while
    the worker still looked healthy -- the reporting failing exactly like the
    thing it is meant to report on.
    """
    try:
        job_metrics.record_queue_depth(await queue_depth(redis))
    except Exception as exc:
        logger.warning("queue_depth_sample_failed", error=str(exc))


async def _poll_queue_depth(redis: Any) -> None:
    while True:
        await record_queue_depth_once(redis)
        await asyncio.sleep(QUEUE_DEPTH_INTERVAL_SECONDS)


async def startup(ctx: dict[str, Any]) -> None:
    settings = Settings()
    configure_logging(settings)
    configure_tracing(settings)
    # Every background job runs in this process and records job.duration and
    # job.dead_letters. Without a meter provider those go to the no-op proxy
    # and are discarded without error, leaving the async dashboard showing a
    # queue with work in it and no jobs ever running.
    configure_metrics(settings)
    instrument()
    if not settings.redis_url:
        raise RuntimeError(
            "CMC_REDIS_URL is not set. The worker would connect to localhost and "
            "idle forever consuming nothing, which looks like a quiet queue "
            "rather than a broken deployment."
        )
    # The CronJob also reports depth -- it must, since it keeps running when
    # this process is not -- but only every fifteen minutes, so the series goes
    # stale in between and the panel reads "no data" rather than "empty queue".
    if ctx.get("redis") is not None:
        ctx["queue_depth_task"] = asyncio.create_task(_poll_queue_depth(ctx["redis"]))
    logger.info("worker_started", max_tries=MAX_TRIES)


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_stopping")
    task = ctx.get("queue_depth_task")
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    # A worker pod is stopped on every deploy. Both providers export on timers,
    # so anything buffered when the signal arrived is lost unless it is
    # flushed -- and a job that failed just before a rollout is precisely the
    # one worth keeping.
    flush_tracing()
    flush_metrics()


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
