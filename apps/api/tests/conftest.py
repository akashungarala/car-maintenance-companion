from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

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


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Real Redis, one container per session.

    Same reasoning as the database: fakeredis diverges from the real server in
    exactly the places a queue depends on — blocking pops, expiry semantics and
    script atomicity.
    """
    container = DockerContainer("redis:7-alpine").with_exposed_ports(6379)
    container.waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}"
