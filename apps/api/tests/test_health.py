"""Liveness endpoint.

The defining property of `/health` is what it does *not* do: it must never
touch Postgres, Redis or any other external dependency. Kubernetes restarts a
container whose liveness probe fails, so a liveness check that depends on the
database turns a brief database blip into a cluster-wide restart storm.
"""

from httpx import AsyncClient

from app.health import ReadinessRegistry


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_reports_service_identity(client: AsyncClient) -> None:
    body = (await client.get("/health")).json()

    assert body["service"] == "cmc-api"
    assert body["version"]


async def test_health_never_runs_readiness_checks(
    client: AsyncClient, registry: ReadinessRegistry
) -> None:
    calls: list[str] = []

    async def spy() -> bool:
        calls.append("called")
        return True

    registry.register("database", spy)

    await client.get("/health")

    assert calls == [], "liveness must not depend on external systems"


async def test_health_echoes_a_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.headers["x-request-id"]


async def test_health_reuses_an_inbound_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"
