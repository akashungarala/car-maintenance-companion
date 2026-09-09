"""Worker startup.

The worker is where every background job runs, so anything it fails to
configure at startup is missing for all of them -- silently, because a metric
sent to an unconfigured provider is discarded without error.
"""

from typing import Any

import pytest

from app import worker


async def test_startup_configures_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """job.duration and job.dead_letters are recorded in this process.

    Without a meter provider they go to the no-op proxy and vanish, and the
    async dashboard shows a queue with work in it and no jobs ever running.
    """
    configured: list[str] = []
    monkeypatch.setattr(worker, "configure_metrics", lambda _s: configured.append("metrics"))
    monkeypatch.setattr(worker, "configure_tracing", lambda _s: configured.append("tracing"))
    monkeypatch.setattr(worker, "instrument", lambda: None)
    monkeypatch.setenv("CMC_REDIS_URL", "redis://localhost:6379/0")

    ctx: dict[str, Any] = {}
    await worker.startup(ctx)

    assert "metrics" in configured, "the worker records job metrics but installs no meter provider"
    assert "tracing" in configured


async def test_shutdown_flushes_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker pod is stopped on every deploy.

    Both providers export on timers, so whatever was buffered when the signal
    arrived is lost unless it is flushed -- and a job that failed just before a
    rollout is exactly the one worth keeping.
    """
    flushed: list[str] = []
    monkeypatch.setattr(worker, "flush_tracing", lambda: flushed.append("traces"))
    monkeypatch.setattr(worker, "flush_metrics", lambda: flushed.append("metrics"))

    await worker.shutdown({})

    assert flushed == ["traces", "metrics"] or set(flushed) == {"traces", "metrics"}
