"""Readiness endpoint.

`/ready` answers a different question from `/health`: not "is the process
alive" but "can this instance serve traffic". It therefore *does* check
dependencies, and returns 503 so Kubernetes removes the pod from the Service
endpoints without restarting it.

The registry is empty in F2 by design. F6 registers the database check and F7
registers Redis; the contract is proven before either exists.
"""

from httpx import AsyncClient

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
