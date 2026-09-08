"""Background tasks.

Phase 0 deliberately has no product work here. The heartbeat exists to prove
the async path, its failure handling and its telemetry before any real job
depends on them — the same reasoning as a Hello World frontend.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.queue import DEAD_LETTER_KEY, DEAD_LETTER_MAX, JobOutcome

logger = structlog.get_logger()


async def heartbeat(ctx: dict[str, Any]) -> dict[str, str]:
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

    async def wrapper(ctx: dict[str, Any]) -> Any:
        try:
            return await func(ctx)
        except Exception as exc:
            if int(ctx.get("job_try", 1)) >= max_tries:
                await record_dead_letter(ctx, JobOutcome(function=func.__name__, error=str(exc)))
            raise

    wrapper.__name__ = func.__name__
    return wrapper
