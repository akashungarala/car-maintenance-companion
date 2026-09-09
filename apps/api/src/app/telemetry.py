"""OpenTelemetry setup.

The application speaks OTLP and nothing else. The Collector is the only
component that knows a vendor exists, so replacing Grafana Cloud with a
self-hosted stack is a Collector exporter change and zero edits here
(ADR-0004).
"""

from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import (
    DropAggregation,
    ExplicitBucketHistogramAggregation,
    View,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased

from app.settings import Settings

_configured = False
_metrics_configured = False

# MILLISECONDS. The instrument records http.server.duration in milliseconds and
# Grafana receives it as http_server_duration_milliseconds, so seconds-shaped
# boundaries would cap the histogram at 5ms while measuring requests that take
# tens to hundreds -- everything piles into +Inf, p95 is unusable, and the
# "p95 > 1.5s" alert can never fire correctly.
#
# Every bucket is a series per label combination. Six, against the SDK default
# of fourteen. 1500 is a boundary on purpose: it is the alert threshold, and
# without it p95 must be interpolated across whichever bucket contains it.
HISTOGRAM_BUCKETS = (5.0, 25.0, 100.0, 250.0, 1500.0, 5000.0)


def _resource(settings: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.version,
            "deployment.environment": settings.environment,
        }
    )


def build_meter_provider(settings: Settings, *, reader: MetricReader) -> MeterProvider:
    """A meter provider reading through the given reader.

    Split out from configure_metrics so tests can read metrics in memory
    instead of needing a collector to export to.
    """
    return MeterProvider(
        resource=_resource(settings),
        metric_readers=[reader],
        views=[
            View(
                instrument_name="http.server.duration",
                aggregation=ExplicitBucketHistogramAggregation(HISTOGRAM_BUCKETS),
            ),
            # Dropped, not re-bucketed. We never ask a question that
            # response-size percentiles answer, and each histogram costs seven
            # series per label combination against a 10,000 cap. A single
            # instrument_type=Histogram view would also have applied the
            # latency boundaries to these, bucketing bytes by milliseconds.
            View(instrument_name="http.server.response.size", aggregation=DropAggregation()),
            View(instrument_name="http.server.request.size", aggregation=DropAggregation()),
        ],
    )


def configure_metrics(settings: Settings) -> None:
    """Install a meter provider, if an endpoint is configured.

    A no-op without one, for the same reason tracing is: local development and
    the tests must not require a running collector.
    """
    global _metrics_configured
    if _metrics_configured or not settings.otlp_endpoint:
        return

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{settings.otlp_endpoint}/v1/metrics"),
        # Slower than the default 60s would be cheaper still, but alerts
        # evaluate on five-minute windows and need several points inside one.
        export_interval_millis=30_000,
    )
    metrics.set_meter_provider(build_meter_provider(settings, reader=reader))
    _metrics_configured = True


def configure_tracing(settings: Settings) -> None:
    """Install a tracer provider, if an endpoint is configured.

    Without an endpoint this is a no-op rather than an error: local development
    and the tests must not require a collector to be running, or every
    contributor needs one to start the app.
    """
    global _configured
    if _configured or not settings.otlp_endpoint:
        return

    resource = _resource(settings)

    # ParentBased means a sampling decision made upstream is honoured, so a
    # sampled request stays whole rather than losing its downstream spans.
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(
            root=ALWAYS_ON
            if settings.trace_sample_ratio >= 1.0
            else TraceIdRatioBased(settings.trace_sample_ratio)
        ),
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otlp_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    _configured = True


def flush_tracing(timeout_millis: int = 5000) -> None:
    """Export anything still buffered.

    BatchSpanProcessor exports on a timer. A long-running server always reaches
    the next tick, but a short-lived process -- the heartbeat CronJob -- exits
    well inside that window and its spans are simply discarded. That silently
    removes the enqueue end of every async trace, leaving the worker's job
    looking like an unexplained root span.
    """
    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if force_flush is not None:  # a no-op provider when tracing is unconfigured
        force_flush(timeout_millis)


def instrument(app: Any = None, *, engine: Any = None) -> None:
    """Attach auto-instrumentation.

    Imported lazily so the packages are only needed where they are used, and a
    missing optional instrumentation degrades to no tracing for that library
    rather than a failed startup.
    """
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            # The probes run every few seconds forever. Tracing them would bury
            # real traffic and burn the 50 GB trace allowance on nothing.
            excluded_urls="health,ready",
        )

    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()


def inject_trace_context(carrier: dict[str, str]) -> dict[str, str]:
    """Write the current trace context into a carrier for the queue.

    Without this the enqueue and the execution are two unrelated traces, and
    "why was this job slow" cannot be answered from the request that caused it.
    """
    inject(carrier)
    return carrier


def restore_trace_context(carrier: dict[str, str]) -> Any:
    """Rebuild the context a job was enqueued with.

    An empty or absent carrier is safe: jobs enqueued by hand, or before this
    shipped, simply start their own trace.
    """
    return extract(carrier)
