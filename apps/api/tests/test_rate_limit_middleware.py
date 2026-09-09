"""Applying the limit to requests.

The middleware decides three things: who the caller is, which budget applies,
and what never counts at all.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings
from tests.conftest import points_for

pytestmark = pytest.mark.integration


def build(redis_url: str, **overrides: object):  # type: ignore[no-untyped-def]
    settings = Settings(
        environment="test",
        log_format="json",
        redis_url=redis_url,
        rate_limit_per_minute=3,
        auth_rate_limit_per_minute=2,
        **overrides,  # type: ignore[arg-type]
    )
    return create_app(settings=settings, readiness=ReadinessRegistry())


@pytest.fixture
async def flushed(redis_url: str) -> str:
    from app.cache import build_client

    client = build_client(redis_url)
    await client.flushdb()
    await client.aclose()
    return redis_url


async def test_probes_are_never_rate_limited(flushed: str) -> None:
    """Kubernetes probes every few seconds, forever, from one address.

    Limiting them would fail readiness, remove the pod from the Service, then
    fail liveness and restart it -- the rate limiter causing exactly the
    outage it exists to prevent, across every pod at once.
    """
    app = build(flushed)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            for _ in range(10):
                assert (await client.get("/health")).status_code == 200
                assert (await client.get("/ready")).status_code == 200
    finally:
        await app.state.cache.aclose()


async def test_requests_beyond_the_budget_get_429_with_retry_after(flushed: str) -> None:
    app = build(flushed)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            headers = {"CF-Connecting-IP": "203.0.113.10"}
            for _ in range(3):
                assert (await client.get("/openapi.json", headers=headers)).status_code == 200

            response = await client.get("/openapi.json", headers=headers)

            assert response.status_code == 429
            assert int(response.headers["Retry-After"]) > 0
    finally:
        await app.state.cache.aclose()


async def test_callers_are_identified_by_the_cloudflare_header(flushed: str) -> None:
    """Without this every request shares one bucket.

    The peer address is Traefik's pod IP, not the caller's, so a per-client
    limit keyed on it is really a global limit: one busy client would lock out
    everyone.
    """
    app = build(flushed)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            for _ in range(3):
                await client.get("/openapi.json", headers={"CF-Connecting-IP": "203.0.113.20"})

            other = await client.get("/openapi.json", headers={"CF-Connecting-IP": "203.0.113.21"})

            assert other.status_code == 200, "budgets are shared between distinct callers"
    finally:
        await app.state.cache.aclose()


async def test_rejections_are_counted(flushed: str, metric_reader: object) -> None:
    """A limit nobody can see is a limit nobody can tune.

    Acceptance for F9 is "enforced *and observable*".
    """
    app = build(flushed)
    before = sum(p.value for p in points_for(metric_reader, "rate_limit.rejected"))  # type: ignore[arg-type]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            headers = {"CF-Connecting-IP": "203.0.113.30"}
            for _ in range(5):
                await client.get("/openapi.json", headers=headers)
    finally:
        await app.state.cache.aclose()

    after = sum(p.value for p in points_for(metric_reader, "rate_limit.rejected"))  # type: ignore[arg-type]
    assert after > before


async def test_rejection_metrics_never_carry_the_caller_address(
    flushed: str, metric_reader: object
) -> None:
    """The bucket is per caller, so it necessarily contains an address.

    The *metric* must not. One label carrying an IP is an unbounded series
    generator against a 10,000 cap, and it puts a personal identifier into a
    store where it is neither needed nor expected.
    """
    app = build(flushed)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            headers = {"CF-Connecting-IP": "203.0.113.40"}
            for _ in range(5):
                await client.get("/openapi.json", headers=headers)
    finally:
        await app.state.cache.aclose()

    points = points_for(metric_reader, "rate_limit.rejected")  # type: ignore[arg-type]
    assert points, "no rejection was recorded, so this test proves nothing"
    values = {str(v) for point in points for v in point.attributes.values()}
    assert not any("203.0.113" in value for value in values), (
        f"the caller address leaked into metric labels: {sorted(values)}"
    )
