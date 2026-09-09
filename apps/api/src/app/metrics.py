"""Metrics for the async path.

Kept separate from telemetry.py, which owns SDK wiring. This module owns the
instruments themselves and, more importantly, the attributes they carry.

The cardinality rule is absolute: an attribute may only take values from a set
we control and can count. `job` is the name of a function we wrote. `outcome`
is one of two strings. `job_id`, `trace_id` and any user or vehicle identifier
are forbidden here -- they belong in logs and traces, where a distinct value
costs nothing, rather than in metrics, where each one is a permanent series
against a 10,000 cap.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import metrics

# The proxy meter forwards to whatever provider is installed later, so these
# are safe to build at import time even though configure_metrics runs during
# application startup.
_meter = metrics.get_meter("app")

JOB_DURATION = _meter.create_histogram(
    "job.duration",
    unit="ms",
    description="Wall-clock duration of a background job attempt",
)

DEAD_LETTERS = _meter.create_counter(
    "job.dead_letters",
    description="Jobs that exhausted their retries",
)

MAGIC_LINKS_REQUESTED = _meter.create_counter(
    "auth.magic_links_requested",
    description="Sign-in links requested",
)

RATE_LIMIT_REJECTED = _meter.create_counter(
    "rate_limit.rejected",
    description="Requests refused by the rate limiter",
)

QUEUE_DEPTH = _meter.create_gauge(
    "queue.depth",
    description="Jobs waiting to be picked up",
)


@contextmanager
def record_job(job: str) -> Iterator[None]:
    """Time one job attempt and record how it ended.

    Duration is recorded on failure too. A job that fails slowly and a job that
    fails instantly are different problems, and only the timing distinguishes
    a broken dependency from a broken argument.
    """
    started = time.perf_counter()
    outcome = "ok"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        JOB_DURATION.record(elapsed_ms, {"job": job, "outcome": outcome})


def record_dead_letter(job: str) -> None:
    """Count a job that gave up.

    The dead-letter list is trimmed to a hundred entries so it cannot itself
    become the outage, which means its length is not a total. This counter is
    the only thing that can answer "has anything given up since the deploy".
    """
    DEAD_LETTERS.add(1, {"job": job})


def record_queue_depth(depth: int) -> None:
    """Record queue depth as a level, not an accumulation.

    Recorded by the CronJob, which already computes it on every run. That also
    means depth keeps being reported when the worker is down -- which is
    exactly the moment the number matters.
    """
    QUEUE_DEPTH.set(depth)


def record_rate_limit_rejection(bucket: str) -> None:
    """Count a refusal.

    Labelled with the bucket ("api" or "auth") and nothing else. The caller's
    address identifies the bucket in Redis, but as a metric label it would be
    an unbounded series generator against a 10,000 cap -- and it would put a
    personal identifier into a store that neither needs nor expects one. Which
    caller was refused belongs in the log line.
    """
    RATE_LIMIT_REJECTED.add(1, {"bucket": bucket})


def record_magic_link_requested() -> None:
    """Count a sign-in request.

    No attributes at all. The address is the only thing that distinguishes one
    request from another, and it is a personal identifier -- as a label it
    would be both an unbounded series generator and a privacy problem. The
    number alone answers what this metric is for: how much of the 100/day email
    budget sign-ins are consuming.
    """
    MAGIC_LINKS_REQUESTED.add(1)
