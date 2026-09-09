"""Rate limiting.

Against real Redis, not a fake: the limiter depends on atomic increment,
expiry semantics and script execution, which is precisely where fakes diverge
from the server.

Two limits, from the plan: 5/min/IP on authentication, 100/min on everything
else. Phase 0 has no auth routes yet, so the auth limit is configured and
proven here rather than left to be discovered when E1-001 adds sign-in.
"""

import asyncio

import pytest

from app.rate_limit import RateLimiter

pytestmark = pytest.mark.integration


@pytest.fixture
async def limiter(redis_url: str):  # type: ignore[no-untyped-def]
    from app.cache import build_client

    client = build_client(redis_url)
    await client.flushdb()
    yield RateLimiter(client)
    await client.aclose()


async def test_requests_under_the_limit_are_allowed(limiter: RateLimiter) -> None:
    for _ in range(5):
        decision = await limiter.check("client-a", limit=5, window_seconds=60)
        assert decision.allowed


async def test_the_request_over_the_limit_is_rejected(limiter: RateLimiter) -> None:
    for _ in range(5):
        await limiter.check("client-b", limit=5, window_seconds=60)

    decision = await limiter.check("client-b", limit=5, window_seconds=60)

    assert not decision.allowed
    assert decision.retry_after > 0, "a 429 without Retry-After tells the caller nothing"


async def test_clients_have_independent_budgets(limiter: RateLimiter) -> None:
    """One noisy client must not be able to deny service to everyone else."""
    for _ in range(5):
        await limiter.check("client-c", limit=5, window_seconds=60)

    decision = await limiter.check("client-d", limit=5, window_seconds=60)

    assert decision.allowed


async def test_the_window_expires(limiter: RateLimiter) -> None:
    """A counter that never expires is a permanent ban, not a rate limit."""
    for _ in range(2):
        await limiter.check("client-e", limit=2, window_seconds=1)
    assert not (await limiter.check("client-e", limit=2, window_seconds=1)).allowed

    await asyncio.sleep(1.2)

    assert (await limiter.check("client-e", limit=2, window_seconds=1)).allowed


async def test_the_counter_always_carries_an_expiry(limiter: RateLimiter) -> None:
    """INCR then EXPIRE as two commands can leave a key with no TTL if the
    process dies between them -- and that key locks its client out forever.
    The two must be atomic.
    """
    await limiter.check("client-f", limit=5, window_seconds=60)

    ttl = await limiter._redis.ttl("ratelimit:client-f")
    assert ttl > 0, "counter has no TTL; this client is locked out permanently"


async def test_a_redis_outage_does_not_deny_service(redis_url: str) -> None:
    """Fail open, loudly.

    A limiter that rejects every request when Redis blips converts a dependency
    outage into a full outage. The abuse it would have prevented is far cheaper
    than the downtime it would cause, so it allows the request and records that
    it could not enforce.
    """
    from app.cache import build_client

    client = build_client("redis://127.0.0.1:1")  # nothing listening
    limiter = RateLimiter(client)

    decision = await limiter.check("client-g", limit=1, window_seconds=60)

    assert decision.allowed
    assert decision.enforced is False, "an unenforced allow must be distinguishable from a real one"
    await client.aclose()
