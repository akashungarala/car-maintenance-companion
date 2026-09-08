"""Database connectivity and the readiness check that depends on it."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import ProgrammingError

from app.database import Database
from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.integration


async def test_connects_to_a_real_postgres(postgres_url: str) -> None:
    db = Database(postgres_url)

    assert await db.is_healthy() is True

    await db.dispose()


async def test_reports_unhealthy_when_the_server_is_unreachable() -> None:
    # Port 1 is reserved and nothing listens there, so this fails fast rather
    # than hanging for the connect timeout.
    db = Database("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/absent")

    assert await db.is_healthy() is False

    await db.dispose()


async def test_raises_on_a_bad_query_rather_than_swallowing_it(postgres_url: str) -> None:
    """is_healthy() must not become a blanket exception sink.

    A health check that returns False for every possible failure hides real
    bugs; only connectivity failures should be absorbed.
    """
    db = Database(postgres_url)

    with pytest.raises(ProgrammingError):
        await db.execute_scalar("SELECT * FROM a_table_that_does_not_exist")

    await db.dispose()


async def test_readiness_reports_the_database(postgres_url: str) -> None:
    settings = Settings(environment="test", database_url=postgres_url)
    registry = ReadinessRegistry(timeout_seconds=5.0)
    app = create_app(settings=settings, readiness=registry)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        body = (await client.get("/ready")).json()

    assert body["status"] == "ready"
    assert body["checks"]["database"]["healthy"] is True


async def test_readiness_fails_when_the_database_is_down() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://nobody:nothing@127.0.0.1:1/absent",
    )
    app = create_app(settings=settings, readiness=ReadinessRegistry(timeout_seconds=5.0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"]["healthy"] is False


async def test_liveness_still_ignores_the_database() -> None:
    """The whole point of /health: a database outage must not restart pods."""
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://nobody:nothing@127.0.0.1:1/absent",
    )
    app = create_app(settings=settings, readiness=ReadinessRegistry(timeout_seconds=5.0))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/health")

    assert response.status_code == 200


async def test_no_database_check_registered_when_unconfigured() -> None:
    """Phase 0 ran without a database; that must keep working."""
    app = create_app(settings=Settings(environment="test"), readiness=ReadinessRegistry())

    assert "database" not in app.state.readiness.names
