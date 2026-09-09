"""Metrics for the async path.

The async dashboard answers four questions -- is work piling up, how long does
it take, is it failing, has anything given up entirely -- and none of them can
be answered from logs alone at a glance. These are the metrics behind them, and
the cardinality constraints that keep them affordable.
"""

from typing import Any

import pytest

from app import metrics as app_metrics
from app.queue import JobOutcome
from app.tasks import record_dead_letter, with_dead_letter
from tests.conftest import points_for


class FakeRedis:
    def __init__(self) -> None:
        self.pushed: list[str] = []

    async def lpush(self, _key: str, value: str) -> None:
        self.pushed.append(value)

    async def ltrim(self, _key: str, _start: int, _stop: int) -> None:
        return None


async def test_successful_job_records_duration_and_outcome(metric_reader: Any) -> None:
    async def work(_ctx: dict[str, Any]) -> str:
        return "done"

    wrapped = with_dead_letter(work, max_tries=3)
    await wrapped({"job_id": "job-aaaa-1111", "job_try": 1})

    points = points_for(metric_reader, "job.duration")
    assert points, "no job duration was recorded"
    outcomes = {p.attributes.get("outcome") for p in points}
    assert "ok" in outcomes


async def test_failed_job_records_an_error_outcome(metric_reader: Any) -> None:
    async def work(_ctx: dict[str, Any]) -> str:
        raise RuntimeError("boom")

    wrapped = with_dead_letter(work, max_tries=3)
    with pytest.raises(RuntimeError):
        await wrapped({"job_id": "job-bbbb-2222", "job_try": 1})

    outcomes = {p.attributes.get("outcome") for p in points_for(metric_reader, "job.duration")}
    assert "error" in outcomes, "a failed job must be distinguishable from a successful one"


async def test_job_metrics_never_label_on_job_id(metric_reader: Any) -> None:
    """job_id is unique per job. As a label it is an unbounded series generator.

    It belongs in logs and traces, where a distinct value costs nothing.
    """

    async def work(_ctx: dict[str, Any]) -> str:
        return "done"

    wrapped = with_dead_letter(work, max_tries=3)
    await wrapped({"job_id": "job-cccc-3333", "job_try": 1})

    values = {
        str(v) for p in points_for(metric_reader, "job.duration") for v in p.attributes.values()
    }
    assert values, "no attributes at all; this test would pass on an empty set"
    assert not any("cccc-3333" in v for v in values), (
        f"job_id leaked into metric labels: {sorted(values)}"
    )


async def test_dead_letters_are_counted(metric_reader: Any) -> None:
    """The dead-letter list is trimmed to 100, so its length is not a total.

    A counter is the only thing that can answer "has anything given up since
    the last deploy" once more than a hundred jobs have failed.
    """
    before = sum(p.value for p in points_for(metric_reader, "job.dead_letters"))

    await record_dead_letter(
        {"job_id": "job-dddd-4444", "job_try": 3, "redis": FakeRedis()},
        JobOutcome(function="heartbeat", error="boom"),
    )

    after = sum(p.value for p in points_for(metric_reader, "job.dead_letters"))
    assert after == before + 1


def test_queue_depth_is_recordable(metric_reader: Any) -> None:
    """Recorded by the CronJob, which already computes it on every run.

    A gauge rather than a counter: depth is a level, not an accumulation.
    """
    app_metrics.record_queue_depth(42)

    points = points_for(metric_reader, "queue.depth")
    assert points and points[-1].value == 42
