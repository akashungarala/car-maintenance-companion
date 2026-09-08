from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", log_format="json", log_level="INFO")


@pytest.fixture
def registry() -> ReadinessRegistry:
    return ReadinessRegistry(timeout_seconds=0.05)


@pytest.fixture
def app(settings: Settings, registry: ReadinessRegistry):  # type: ignore[no-untyped-def]
    return create_app(settings=settings, readiness=registry)


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Real PostgreSQL, one container per session.

    Never SQLite. Testing against SQLite while running Postgres in production
    is a well-known source of false green builds: JSONB, arrays, ON CONFLICT,
    timezone handling, constraint semantics and transactional DDL all differ.
    See docs/engineering/testing.md.
    """
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()
