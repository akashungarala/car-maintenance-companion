"""Background tasks.

Phase 0 deliberately has no product work here. The heartbeat exists to prove
the async path, its failure handling and its telemetry before any real job
depends on them — the same reasoning as a Hello World frontend.
"""

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.queue import DEAD_LETTER_KEY, DEAD_LETTER_MAX, JobOutcome

logger = structlog.get_logger()


async def heartbeat(
    ctx: dict[str, Any], trace_carrier: dict[str, str] | None = None
) -> dict[str, str]:
    """The heartbeat itself. No product logic — see the module docstring.

    Runs inside a span linked to whatever enqueued it, so a slow or failing job
    is reachable from the request or schedule that caused it.
    """
    from opentelemetry import trace

    from app.telemetry import restore_trace_context

    tracer = trace.get_tracer("app.tasks")
    parent = restore_trace_context(trace_carrier or {})
    with tracer.start_as_current_span("heartbeat", context=parent):
        logger.info("heartbeat", job_id=ctx.get("job_id"), attempt=ctx.get("job_try"))
        return {"status": "ok"}


async def record_dead_letter(ctx: dict[str, Any], outcome: JobOutcome) -> None:
    """Record a job that exhausted its retries.

    Without this a permanently failing job disappears: ARQ drops it after the
    final attempt and nothing remains to alert on or investigate. The list is
    trimmed so the failure handler cannot itself become the outage.
    """
    entry = json.dumps(
        {
            "job_id": ctx.get("job_id"),
            "function": outcome.function,
            "attempts": ctx.get("job_try"),
            "error": outcome.error,
        }
    )
    redis = ctx["redis"]
    await redis.lpush(DEAD_LETTER_KEY, entry)
    await redis.ltrim(DEAD_LETTER_KEY, 0, DEAD_LETTER_MAX - 1)
    logger.error(
        "job_dead_lettered",
        job_id=ctx.get("job_id"),
        function=outcome.function,
        attempts=ctx.get("job_try"),
    )


def with_dead_letter(
    func: Callable[[dict[str, Any]], Awaitable[Any]], *, max_tries: int
) -> Callable[[dict[str, Any]], Awaitable[Any]]:
    """Record to the dead-letter list only when retries are exhausted.

    Dead-lettering on every failed attempt would mean a job that succeeds on
    its third try still leaves two entries behind, and the list stops meaning
    "needs attention". The exception is always re-raised so ARQ still owns
    retry scheduling.
    """

    @functools.wraps(func)
    async def wrapper(ctx: dict[str, Any], **kwargs: Any) -> Any:
        try:
            return await func(ctx, **kwargs)
        except Exception as exc:
            if int(ctx.get("job_try", 1)) >= max_tries:
                await record_dead_letter(ctx, JobOutcome(function=func.__name__, error=str(exc)))
            raise

    return wrapper
