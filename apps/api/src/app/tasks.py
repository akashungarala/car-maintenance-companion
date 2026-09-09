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

from app import metrics as job_metrics
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


async def send_magic_link_email(
    ctx: dict[str, Any],
    *,
    email: str,
    token: str,
    base_url: str,
    trace_carrier: dict[str, str] | None = None,
    sender: Any = None,
) -> dict[str, str]:
    """Send one sign-in link.

    The token arrives in the job payload because the email is the only place it
    may legitimately appear. It is never logged here, and no line in this
    function includes the arguments -- adding one while debugging would put
    working sign-in links into log storage.
    """
    from opentelemetry import trace

    from app import metrics as job_metrics
    from app.identity.email import build_sender
    from app.settings import Settings
    from app.telemetry import restore_trace_context

    tracer = trace.get_tracer("app.tasks")
    parent = restore_trace_context(trace_carrier or {})
    with tracer.start_as_current_span("send_magic_link_email", context=parent):
        # The API cannot infer the browser's URL: it is reached through
        # Cloudflare, Traefik and a path prefix, so a link built from the
        # incoming request would point somewhere unreachable.
        link = f"{base_url.rstrip('/')}/auth/callback?token={token}"
        active = sender if sender is not None else build_sender(Settings())

        await active.send_magic_link(email=email, link=link)

        job_metrics.record_email_sent("magic_link")
        logger.info("magic_link_email_sent", job_id=ctx.get("job_id"))
        return {"status": "sent"}


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
    # The list is trimmed to a hundred entries, so its length stops being a
    # total. Only a counter can answer "has anything given up since the deploy".
    job_metrics.record_dead_letter(outcome.function)


def with_dead_letter(
    # Callable[..., ] rather than a fixed signature: the wrapper forwards
    # **kwargs, so jobs take whatever their payload carries. The narrower type
    # described the heartbeat rather than the decorator.
    func: Callable[..., Awaitable[Any]],
    *,
    max_tries: int,
) -> Callable[..., Awaitable[Any]]:
    """Record to the dead-letter list only when retries are exhausted.

    Dead-lettering on every failed attempt would mean a job that succeeds on
    its third try still leaves two entries behind, and the list stops meaning
    "needs attention". The exception is always re-raised so ARQ still owns
    retry scheduling.
    """

    @functools.wraps(func)
    async def wrapper(ctx: dict[str, Any], **kwargs: Any) -> Any:
        # Wraps every job, so timing here covers all of them without each one
        # remembering to instrument itself.
        try:
            with job_metrics.record_job(func.__name__):
                return await func(ctx, **kwargs)
        except Exception as exc:
            if int(ctx.get("job_try", 1)) >= max_tries:
                await record_dead_letter(ctx, JobOutcome(function=func.__name__, error=str(exc)))
            raise

    return wrapper
