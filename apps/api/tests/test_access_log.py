"""The access log emitted by the request middleware."""

from typing import Any

import structlog
from httpx import AsyncClient


async def test_request_is_logged_with_correlation_fields(client: AsyncClient) -> None:
    with structlog.testing.capture_logs() as logs:
        await client.get("/health", headers={"X-Request-ID": "req-42"})

    entry = next(log for log in logs if log["event"] == "http_request")

    assert entry["request_id"] == "req-42"
    assert entry["method"] == "GET"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], float)


async def test_route_is_logged_as_a_template_not_a_raw_path(client: AsyncClient) -> None:
    """Metrics label on this field, so it must be bounded cardinality.

    A raw path would make every vehicle id its own time series and exhaust the
    10k active-series budget on the Grafana free tier. See ADR-0004.
    """
    with structlog.testing.capture_logs() as logs:
        await client.get("/health")

    entry: dict[str, Any] = next(log for log in logs if log["event"] == "http_request")

    assert entry["route"] == "/health"


async def test_unmatched_route_is_logged_without_unbounded_cardinality(
    client: AsyncClient,
) -> None:
    with structlog.testing.capture_logs() as logs:
        await client.get("/no/such/path/12345")

    entry = next(log for log in logs if log["event"] == "http_request")

    assert entry["status"] == 404
    assert entry["route"] == "__unmatched__"


async def test_unhandled_exception_is_logged_and_returns_500(app, client: AsyncClient) -> None:  # type: ignore[no-untyped-def]
    """A failing endpoint must still produce an access log and a clean 500.

    The route is registered here rather than in the application: production code
    should not carry a deliberately broken endpoint.
    """

    async def boom() -> None:
        raise RuntimeError("kaboom")

    app.add_api_route("/boom", boom)

    with structlog.testing.capture_logs() as logs:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    entry = next(log for log in logs if log["event"] == "http_request")
    assert entry["status"] == 500
