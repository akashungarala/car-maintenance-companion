"""Queue plumbing.

Redis is used for three things, each with a concrete reason (see the plan's
component table): the ARQ broker here, caching slow external lookups, and
auth rate limiting. It is not present because a queue felt architectural.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from arq.connections import ArqRedis, RedisSettings

# ARQ's default queue name. Named explicitly so the metric and the dead-letter
# key below cannot drift from the queue they describe.
QUEUE_NAME = "arq:queue"
DEAD_LETTER_KEY = "cmc:dead-letter"

# Bounded on purpose. A job failing in a loop would otherwise fill Redis and
# take the queue down with it — the failure handler becoming the outage.
DEAD_LETTER_MAX = 100


@dataclass(frozen=True)
class JobOutcome:
    function: str
    error: str


def build_redis_settings(url: str) -> RedisSettings:
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
        conn_timeout=5,
    )


async def enqueue_heartbeat(pool: ArqRedis, *, job_id: str | None = None) -> object | None:
    """Enqueue the heartbeat.

    Returns None when a job with the same id is already queued. ARQ dedupes on
    job_id, which is what makes a CronJob that fires twice — a retry, an
    overlapping schedule — safe.

    The current trace context travels with the job, so the execution joins the
    trace that enqueued it rather than starting an unrelated one.
    """
    from app.telemetry import inject_trace_context

    return await pool.enqueue_job(
        "heartbeat", _job_id=job_id, trace_carrier=inject_trace_context({})
    )


async def enqueue_magic_link_email(
    pool: ArqRedis, *, email: str, token: str, base_url: str
) -> object | None:
    """Hand the sign-in email to the worker.

    The raw token travels in the job payload because the email is the only
    place it can legitimately appear. It is never written to the database, and
    the payload lives in Redis for as long as the job takes to run.

    No job_id, so no deduplication: two requests within the same minute are two
    distinct links, and the second having invalidated the first is exactly what
    the user expects when they click "send it again".
    """
    from app.telemetry import inject_trace_context

    return await pool.enqueue_job(
        "send_magic_link_email",
        email=email,
        token=token,
        base_url=base_url,
        trace_carrier=inject_trace_context({}),
    )


async def queue_depth(pool: ArqRedis) -> int:
    """Number of jobs waiting. Exported as a metric in F8 and alerted on."""
    return int(await pool.zcard(QUEUE_NAME))
