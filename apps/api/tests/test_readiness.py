"""Readiness endpoint.

`/ready` answers a different question from `/health`: not "is the process
alive" but "can this instance serve traffic". It therefore *does* check
dependencies, and returns 503 so Kubernetes removes the pod from the Service
endpoints without restarting it.

The registry is empty in F2 by design. F6 registers the database check and F7
registers Redis; the contract is proven before either exists.
"""

from httpx import AsyncClient
from opentelemetry.instrumentation.utils import is_instrumentation_enabled

from app.health import ReadinessRegistry


async def test_ready_with_no_dependencies_is_ready(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_ready_reports_each_dependency(
    client: AsyncClient, registry: ReadinessRegistry
) -> None:
    async def healthy() -> bool:
        return True

    registry.register("database", healthy)
    registry.register("redis", healthy)

    body = (await client.get("/ready")).json()

    assert body["checks"] == {
        "database": {"healthy": True, "detail": None},
        "redis": {"healthy": True, "detail": None},
    }


async def test_ready_returns_503_when_a_dependency_is_unhealthy(
    client: AsyncClient, registry: ReadinessRegistry
) -> None:
    async def healthy() -> bool:
        return True

    async def unhealthy() -> bool:
        return False

    registry.register("database", healthy)
    registry.register("redis", unhealthy)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"]["healthy"] is False


async def test_ready_treats_a_raising_check_as_unhealthy(
    client: AsyncClient, registry: ReadinessRegistry
) -> None:
    async def exploding() -> bool:
        raise ConnectionRefusedError("connection refused")

    registry.register("database", exploding)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"]["healthy"] is False
    assert "connection refused" in response.json()["checks"]["database"]["detail"]


async def test_a_slow_check_does_not_hang_readiness(
    client: AsyncClient, registry: ReadinessRegistry
) -> None:
    import asyncio

    async def hangs() -> bool:
        await asyncio.sleep(30)
        return True

    registry.register("database", hangs)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert "timed out" in response.json()["checks"]["database"]["detail"]


async def test_checks_run_with_instrumentation_suppressed() -> None:
    """Probe traffic must not generate spans.

    `/ready` is excluded from HTTP instrumentation, but that only suppresses the
    server span -- the database check inside it still emitted SQLAlchemy spans,
    and with no HTTP span to parent them they arrived as orphan roots. Measured
    at 48 spans/minute in production (2 spans per probe, every 5s, two
    replicas): pure noise burying real traces.
    """
    registry = ReadinessRegistry()
    observed: list[bool] = []

    async def check() -> bool:
        observed.append(is_instrumentation_enabled())
        return True

    registry.register("dependency", check)
    await registry.run_all()

    assert observed == [False], "readiness checks must run with instrumentation suppressed"
    assert is_instrumentation_enabled(), "suppression must not leak past the check"


async def test_suppression_is_released_when_a_check_fails() -> None:
    """A failing check must not leave instrumentation suppressed process-wide.

    The registry swallows check exceptions, so a leak here would silently
    disable tracing for every subsequent request in the process.
    """
    registry = ReadinessRegistry()

    async def boom() -> bool:
        raise RuntimeError("dependency exploded")

    registry.register("dependency", boom)
    await registry.run_all()

    assert is_instrumentation_enabled()
