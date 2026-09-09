from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader


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


@pytest.fixture(scope="session", autouse=True)
def metric_reader() -> "InMemoryMetricReader":
    """A global meter provider the whole session shares.

    set_meter_provider only takes effect once per process, so this is
    session-scoped by necessity rather than for speed, and tests compare
    against a snapshot rather than assuming the reader is empty.

    autouse because otherwise it installs lazily, on first request. Any test
    that configures the real OTLP provider first -- test_cli does, by setting
    CMC_OTLP_ENDPOINT -- would win the race and silently send every metric to a
    collector that is not running, leaving the reader empty and the assertions
    failing for a reason that has nothing to do with the code under test.
    """
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    from app.telemetry import metric_views

    reader = InMemoryMetricReader()
    otel_metrics.set_meter_provider(MeterProvider(metric_readers=[reader], views=metric_views()))
    return reader


def points_for(reader: "InMemoryMetricReader", name: str) -> list[Any]:
    """Every data point recorded for one metric, with its attributes."""
    data = reader.get_metrics_data()
    return [
        point
        for resource_metric in getattr(data, "resource_metrics", [])
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]
