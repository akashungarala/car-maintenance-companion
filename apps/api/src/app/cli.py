"""Entrypoints run by Kubernetes rather than by a person.

`python -m app.cli enqueue` is what the heartbeat CronJob executes.
"""

import asyncio
import sys

import structlog
from arq import create_pool
from opentelemetry import trace

from app.logging import configure_logging
from app.queue import build_redis_settings, enqueue_heartbeat, queue_depth
from app.settings import Settings
from app.telemetry import configure_tracing, flush_tracing

logger = structlog.get_logger()


async def enqueue_main() -> int:
    settings = Settings()
    configure_logging(settings)

    if not settings.redis_url:
        raise RuntimeError(
            "CMC_REDIS_URL is not set. Exiting non-zero rather than doing "
            "nothing quietly: a CronJob that cannot enqueue must look like a "
            "failure, not like a schedule that never fired."
        )

    # The enqueue must happen inside a span. enqueue_heartbeat injects the
    # *current* context into the job, so with no active span the carrier goes
    # out empty and the worker's execution starts an unrelated root trace --
    # exactly what production showed as `heartbeat(trace_carrier={})`.
    configure_tracing(settings)
    tracer = trace.get_tracer("app.cli")

    pool = await create_pool(build_redis_settings(settings.redis_url))
    try:
        with tracer.start_as_current_span("heartbeat.enqueue"):
            job = await enqueue_heartbeat(pool)
            depth = await queue_depth(pool)
            logger.info(
                "heartbeat_enqueued",
                job_id=getattr(job, "job_id", None),
                queue_depth=depth,
                # None means a job with the same id was already queued. Not an
                # error — that is the idempotency guard doing its job.
                deduplicated=job is None,
            )
        return 0
    finally:
        await pool.aclose()
        # This process is about to exit; anything still buffered is lost.
        flush_tracing()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command != "enqueue":
        sys.stderr.write(f"usage: python -m app.cli enqueue (got {command!r})\n")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(enqueue_main()))


if __name__ == "__main__":
    main()
