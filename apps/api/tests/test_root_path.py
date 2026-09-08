"""Serving behind a path-stripping proxy.

In production the API is reached at
akashungarala.com/apps/car-maintenance-companion/api, and the portfolio rewrite
strips that prefix before forwarding. FastAPI must still generate URLs
*including* it, or the docs page loads and then fails to fetch its own schema
from a 404 — a failure that looks like a broken deployment.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings

PREFIX = "/apps/car-maintenance-companion/api"


@pytest.fixture
async def proxied_client() -> AsyncIterator[AsyncClient]:
    app = create_app(
        settings=Settings(environment="test", root_path=PREFIX),
        readiness=ReadinessRegistry(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_openapi_advertises_the_proxied_prefix(proxied_client: AsyncClient) -> None:
    # FastAPI injects root_path into `servers` when the schema is *requested*,
    # not when app.openapi() is called, so this must go through HTTP.
    schema = (await proxied_client.get("/openapi.json")).json()

    assert schema["servers"] == [{"url": PREFIX}]


async def test_docs_fetches_its_schema_through_the_prefix(proxied_client: AsyncClient) -> None:
    body = (await proxied_client.get("/docs")).text

    assert f"{PREFIX}/openapi.json" in body


async def test_routes_stay_unprefixed_so_kubernetes_probes_work(
    proxied_client: AsyncClient,
) -> None:
    """root_path changes generated URLs, not the routes themselves.

    The kubelet reaches the pod directly and knows nothing about the proxy, so
    /health must keep answering without the prefix.
    """
    assert (await proxied_client.get("/health")).status_code == 200
