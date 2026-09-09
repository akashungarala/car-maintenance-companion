"""The CronJob entrypoint.

`python -m app.cli enqueue` is the start of the async trace: whatever context it
injects is what the worker's job span attaches to. If it injects nothing, the
job runs as an unrelated root span and the enqueue->execute link -- the whole
point of propagating context into the queue -- is lost.
"""

from typing import Any

import pytest

from app import cli


class FakePool:
    """Records what was enqueued without needing Redis."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    async def enqueue_job(self, name: str, **kwargs: Any) -> object:
        self.kwargs = kwargs
        return type("Job", (), {"job_id": "test-job"})()

    async def zcard(self, _key: str) -> int:
        return 1

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch) -> FakePool:
    pool = FakePool()

    async def fake_create_pool(*_args: Any, **_kwargs: Any) -> FakePool:
        return pool

    monkeypatch.setattr(cli, "create_pool", fake_create_pool)
    monkeypatch.setenv("CMC_REDIS_URL", "redis://localhost:6379/0")
    return pool


async def test_enqueue_propagates_trace_context(
    fake_pool: FakePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The enqueue must happen inside a span, so the worker joins this trace.

    Without an active span there is nothing to inject and the carrier arrives
    empty, which is what was observed in production: `heartbeat(trace_carrier={})`.
    """
    monkeypatch.setenv("CMC_OTLP_ENDPOINT", "http://collector:4318")
    # Flushing is covered by its own test. Forcing a real export here would
    # block on a collector that does not exist and leave an exporter thread
    # writing to closed streams after the run finishes.
    monkeypatch.setattr(cli, "flush_tracing", lambda: None)

    assert await cli.enqueue_main() == 0

    carrier = fake_pool.kwargs.get("trace_carrier")
    assert carrier, "no trace context was injected; the worker cannot join this trace"
    assert "traceparent" in carrier


async def test_enqueue_still_works_without_a_collector(fake_pool: FakePool) -> None:
    """Tracing is optional. A missing collector must not stop the CronJob."""
    assert await cli.enqueue_main() == 0


async def test_enqueue_flushes_spans_before_exiting(
    fake_pool: FakePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Short-lived processes must flush explicitly.

    BatchSpanProcessor exports on a timer. The CronJob finishes and exits well
    inside that window, so without a forced flush its spans are simply lost --
    and the enqueue end of every async trace disappears with them.
    """
    flushed: list[int] = []
    monkeypatch.setattr(cli, "flush_tracing", lambda: flushed.append(1))
    monkeypatch.setenv("CMC_OTLP_ENDPOINT", "http://collector:4318")

    await cli.enqueue_main()

    assert flushed, "spans were not flushed; a short-lived process loses them"


async def test_enqueue_flushes_metrics_before_exiting(
    fake_pool: FakePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Queue depth is recorded here and nowhere else.

    The periodic metric reader exports on a 30-second timer that this process
    never reaches, so without an explicit flush the gauge is recorded correctly
    and then discarded -- and the queue-depth alert has no data at exactly the
    moment the queue is backing up.
    """
    flushed: list[int] = []
    monkeypatch.setattr(cli, "flush_metrics", lambda: flushed.append(1))
    monkeypatch.setattr(cli, "flush_tracing", lambda: None)
    monkeypatch.setenv("CMC_OTLP_ENDPOINT", "http://collector:4318")

    await cli.enqueue_main()

    assert flushed, "metrics were not flushed; the queue depth gauge is lost"
