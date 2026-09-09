"""Application metrics, and the cardinality discipline that keeps them affordable.

The free tier allows 10,000 active series. One label carrying a unique value
per request exhausts that in an afternoon, and the failure is silent: Grafana
drops the overflow and the dashboards simply stop being right. These tests
guard the two decisions that prevent it -- bounded histogram buckets, and never
labelling on anything unbounded.
"""

from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.settings import Settings
from app.telemetry import HISTOGRAM_BUCKETS, build_meter_provider, configure_metrics


def _collect(reader: InMemoryMetricReader) -> list[Any]:
    data = reader.get_metrics_data()
    metrics = []
    for resource_metric in getattr(data, "resource_metrics", []):
        for scope_metric in resource_metric.scope_metrics:
            metrics.extend(scope_metric.metrics)
    return metrics


def test_configure_metrics_is_a_no_op_without_an_endpoint() -> None:
    """Local development and the tests must not require a collector."""
    configure_metrics(Settings(environment="test"))  # must not raise


def test_histogram_buckets_are_bounded_and_in_milliseconds() -> None:
    """Each bucket is a series, per label combination.

    The SDK default is fourteen boundaries; six cover what we alert on at under
    half the series cost.

    The unit matters more than the count. The instrument records
    http.server.duration in *milliseconds* -- Grafana receives it as
    http_server_duration_milliseconds -- so seconds-shaped boundaries put a
    5ms ceiling on a histogram measuring requests that take tens or hundreds of
    milliseconds. Everything lands in +Inf, p95 becomes unusable, and the
    "p95 > 1.5s" alert can never fire correctly.
    """
    assert len(HISTOGRAM_BUCKETS) == 6
    assert list(HISTOGRAM_BUCKETS) == sorted(HISTOGRAM_BUCKETS), "buckets must ascend"
    assert 1500 in HISTOGRAM_BUCKETS, (
        "the latency alert fires at p95 > 1.5s, which in milliseconds is 1500. "
        "Without a boundary there, p95 is interpolated across whatever bucket "
        "contains the threshold."
    )
    assert max(HISTOGRAM_BUCKETS) >= 1500, (
        "the top boundary is below the alert threshold, so every slow request "
        "is indistinguishable from every other slow request"
    )


async def test_size_histograms_are_dropped() -> None:
    """We never ask a question that response-size percentiles answer.

    Each one costs seven series per label combination, against a 10,000 cap.
    """
    reader = InMemoryMetricReader()
    provider = build_meter_provider(Settings(environment="test"), reader=reader)

    app = FastAPI()

    @app.get("/vehicles/{vehicle_id}")
    async def _vehicle(vehicle_id: str) -> dict[str, str]:
        return {"id": vehicle_id}

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, meter_provider=provider)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/vehicles/abc")

    names = {metric.name for metric in _collect(reader)}
    assert not [name for name in names if "size" in name], (
        f"size histograms are still being exported: {sorted(names)}"
    )

    FastAPIInstrumentor.uninstrument_app(app)


async def test_request_metrics_never_label_on_raw_paths() -> None:
    """The single most expensive mistake available to us.

    Labelling on the raw path makes every unmatched URL its own series, so any
    crawler hitting /wp-admin, /.env, /admin.php mints series until the cap is
    reached and real metrics start being dropped. The route *template* is
    bounded by the number of routes we wrote.
    """
    reader = InMemoryMetricReader()
    provider = build_meter_provider(Settings(environment="test"), reader=reader)

    app = FastAPI()

    @app.get("/vehicles/{vehicle_id}")
    async def _vehicle(vehicle_id: str) -> dict[str, str]:
        return {"id": vehicle_id}

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, meter_provider=provider)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/vehicles/aaaa-unique-1111")
        await client.get("/vehicles/bbbb-unique-2222")
        await client.get("/definitely-not-a-route-cccc-3333")

    values = {
        str(value)
        for metric in _collect(reader)
        for point in metric.data.data_points
        for value in point.attributes.values()
    }

    # Proves the assertions below are reading real labels rather than an empty
    # set, which would make this test pass no matter what was recorded.
    assert "/vehicles/{vehicle_id}" in values, (
        f"the route template is missing, so this test is inspecting nothing: {sorted(values)}"
    )

    for unbounded in ("aaaa-unique-1111", "bbbb-unique-2222", "cccc-3333"):
        assert not any(unbounded in value for value in values), (
            f"{unbounded!r} appears as a metric label; every distinct URL would "
            f"become its own series. Labels: {sorted(values)}"
        )

    FastAPIInstrumentor.uninstrument_app(app)


async def test_request_metrics_are_actually_recorded() -> None:
    """A metrics pipeline that records nothing would pass the test above."""
    reader = InMemoryMetricReader()
    provider = build_meter_provider(Settings(environment="test"), reader=reader)

    app = FastAPI()

    @app.get("/vehicles/{vehicle_id}")
    async def _vehicle(vehicle_id: str) -> dict[str, str]:
        return {"id": vehicle_id}

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, meter_provider=provider)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/vehicles/abc")

    names = {metric.name for metric in _collect(reader)}
    assert names, "no metrics were recorded at all"
    assert any("duration" in name for name in names), f"no latency metric among {names}"

    FastAPIInstrumentor.uninstrument_app(app)
