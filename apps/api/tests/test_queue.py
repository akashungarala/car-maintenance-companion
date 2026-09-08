"""The async path: enqueue, consume, retry, dead-letter, idempotency.

Phase 0 has no product work to run asynchronously. This exercises the machinery
with a heartbeat job so the path, its failure handling and its metrics are
proven before anything real depends on them.
"""

import pytest
from arq import create_pool

from app.queue import (
    DEAD_LETTER_KEY,
    JobOutcome,
    build_redis_settings,
    enqueue_heartbeat,
    queue_depth,
)
from app.tasks import heartbeat, record_dead_letter, with_dead_letter

pytestmark = pytest.mark.integration


async def test_heartbeat_reports_success() -> None:
    """No product logic: it exists to prove the path end to end."""
    result = await heartbeat({})

    assert result["status"] == "ok"


async def test_enqueue_then_read_queue_depth(redis_url: str) -> None:
    pool = await create_pool(build_redis_settings(redis_url))

    assert await queue_depth(pool) == 0
    await enqueue_heartbeat(pool)

    assert await queue_depth(pool) == 1

    await pool.aclose()


async def test_enqueueing_the_same_key_twice_is_idempotent(redis_url: str) -> None:
    """A CronJob that fires twice — a retry, an overlapping schedule — must not
    produce two runs. ARQ dedupes on job_id while the job is queued."""
    pool = await create_pool(build_redis_settings(redis_url))

    first = await enqueue_heartbeat(pool, job_id="fixed-key")
    second = await enqueue_heartbeat(pool, job_id="fixed-key")

    assert first is not None
    assert second is None, "a duplicate job_id must be rejected, not queued twice"

    await pool.aclose()


async def test_failures_are_recorded_to_a_dead_letter_list(redis_url: str) -> None:
    """A job that exhausts its retries must leave evidence.

    Without this a permanently failing job disappears silently: ARQ drops it
    after the final attempt and nothing remains to alert on or investigate.
    """
    pool = await create_pool(build_redis_settings(redis_url))
    ctx = {"redis": pool, "job_id": "job-1", "job_try": 3}

    await record_dead_letter(ctx, JobOutcome(function="heartbeat", error="boom"))

    entries = await pool.lrange(DEAD_LETTER_KEY, 0, -1)
    assert len(entries) == 1
    assert b"boom" in entries[0]
    assert b"heartbeat" in entries[0]

    await pool.aclose()


async def test_dead_letter_list_is_bounded(redis_url: str) -> None:
    """An unbounded failure list is its own outage: a job failing in a loop
    would fill Redis and take the queue down with it."""
    pool = await create_pool(build_redis_settings(redis_url))
    await pool.delete(DEAD_LETTER_KEY)

    for i in range(120):
        await record_dead_letter(
            {"redis": pool, "job_id": f"j{i}", "job_try": 3},
            JobOutcome(function="heartbeat", error=f"failure {i}"),
        )

    assert await pool.llen(DEAD_LETTER_KEY) <= 100

    await pool.aclose()


async def test_a_failing_job_dead_letters_only_on_the_final_attempt(redis_url: str) -> None:
    """Retries must not each produce a dead-letter entry.

    Otherwise a job that succeeds on attempt three still leaves two entries
    behind, and the list stops meaning "needs attention".
    """
    pool = await create_pool(build_redis_settings(redis_url))
    await pool.delete(DEAD_LETTER_KEY)

    async def always_fails(ctx: dict[str, object]) -> None:
        raise RuntimeError("nope")

    wrapped = with_dead_letter(always_fails, max_tries=3)

    for attempt in (1, 2):
        with pytest.raises(RuntimeError):
            await wrapped({"redis": pool, "job_id": "j", "job_try": attempt})
        assert await pool.llen(DEAD_LETTER_KEY) == 0, "dead-lettered before the last try"

    with pytest.raises(RuntimeError):
        await wrapped({"redis": pool, "job_id": "j", "job_try": 3})

    assert await pool.llen(DEAD_LETTER_KEY) == 1

    await pool.aclose()


async def test_a_succeeding_job_leaves_no_dead_letter(redis_url: str) -> None:
    pool = await create_pool(build_redis_settings(redis_url))
    await pool.delete(DEAD_LETTER_KEY)

    wrapped = with_dead_letter(heartbeat, max_tries=3)
    result = await wrapped({"redis": pool, "job_id": "ok", "job_try": 1})

    assert result["status"] == "ok"
    assert await pool.llen(DEAD_LETTER_KEY) == 0

    await pool.aclose()


def test_worker_module_imports_without_redis_configured() -> None:
    """Import must not depend on configuration.

    ARQ reads settings off the class, so raising during resolution would make
    the module unimportable — including during test collection.
    """
    from app.worker import WorkerSettings

    assert WorkerSettings.max_tries == 3
    assert len(WorkerSettings.functions) == 1


async def test_worker_startup_refuses_when_redis_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failing loudly beats connecting to localhost and idling.

    A worker consuming nothing looks exactly like a quiet queue.
    """
    from app.worker import startup

    monkeypatch.delenv("CMC_REDIS_URL", raising=False)

    with pytest.raises(RuntimeError, match="CMC_REDIS_URL"):
        await startup({})


async def test_enqueue_cli_places_a_job_on_the_queue(
    redis_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CronJob runs this. It must exit non-zero if it cannot enqueue,
    or a broken schedule looks like a schedule that simply never fired."""
    from app.cli import enqueue_main

    monkeypatch.setenv("CMC_REDIS_URL", redis_url)
    pool = await create_pool(build_redis_settings(redis_url))
    before = await queue_depth(pool)

    exit_code = await enqueue_main()

    assert exit_code == 0
    assert await queue_depth(pool) == before + 1
    await pool.aclose()


async def test_enqueue_cli_fails_loudly_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.cli import enqueue_main

    monkeypatch.delenv("CMC_REDIS_URL", raising=False)

    with pytest.raises(RuntimeError, match="CMC_REDIS_URL"):
        await enqueue_main()


def test_the_worker_registers_the_job_under_the_name_that_is_enqueued() -> None:
    """ARQ resolves jobs by __qualname__, not __name__.

    Wrapping the task without functools.wraps registered it as
    `with_dead_letter.<locals>.wrapper`, so every enqueued heartbeat came back
    "function not found" — while tests that called the wrapper directly passed.
    This asserts the name ARQ actually uses.
    """
    from arq.worker import func as arq_func

    from app.worker import WorkerSettings

    registered = {arq_func(f).name for f in WorkerSettings.functions}

    assert "heartbeat" in registered, f"registered under {registered} instead"
