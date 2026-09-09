"""Redis as a readiness dependency.

The API uses Redis for the job queue and, from F9, for rate limiting. An
instance that cannot reach it can still serve reads but cannot enqueue work or
enforce a limit, so it should be taken out of the Service endpoints rather than
left serving traffic it will half-handle.

Liveness deliberately does not check it. A Redis blip must not restart every
pod and turn a recoverable outage into a crash loop.
"""

import pytest
from httpx import AsyncClient

from app.cache import RedisHealth


class FakeRedis:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.closed = False

    async def ping(self) -> bool:
        if self.fail:
            raise self.fail
        return True

    async def aclose(self) -> None:
        self.closed = True


async def test_healthy_when_redis_responds() -> None:
    health = RedisHealth(FakeRedis())

    assert await health.is_healthy() is True


async def test_unhealthy_when_redis_is_unreachable() -> None:
    health = RedisHealth(FakeRedis(fail=ConnectionError("connection refused")))

    assert await health.is_healthy() is False


async def test_programming_errors_are_not_swallowed() -> None:
    """A check that returns False for any exception hides real bugs.

    Only connectivity failures mean "not ready"; anything else means the check
    itself is broken and should be visible as an error, not reported as a
    dependency being down.
    """
    health = RedisHealth(FakeRedis(fail=TypeError("wrong argument")))

    with pytest.raises(TypeError):
        await health.is_healthy()


@pytest.mark.integration
async def test_ready_reports_redis_alongside_the_database(
    redis_url: str, postgres_url: str
) -> None:
    """Acceptance criterion 6 of the Phase 0 demo names both dependencies.

    Against a real Redis, because the point is that the check reaches it.
    """
    from httpx import ASGITransport

    from app.health import ReadinessRegistry
    from app.main import create_app
    from app.settings import Settings

    settings = Settings(
        environment="test", redis_url=redis_url, database_url=postgres_url, log_format="json"
    )
    app = create_app(settings=settings, readiness=ReadinessRegistry())

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
    finally:
        # The lifespan does this in the running app; ASGITransport does not run
        # it, so the test closes the clients itself rather than leaking them.
        await app.state.cache.aclose()
        await app.state.database.dispose()

    body = response.json()
    assert response.status_code == 200, body
    assert "redis" in body["checks"], (
        "readiness does not report Redis, so an instance that cannot enqueue "
        "work still receives traffic"
    )
    assert body["checks"]["redis"]["healthy"] is True
