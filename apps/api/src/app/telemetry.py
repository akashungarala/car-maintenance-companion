"""OpenTelemetry setup.

The application speaks OTLP and nothing else. The Collector is the only
component that knows a vendor exists, so replacing Grafana Cloud with a
self-hosted stack is a Collector exporter change and zero edits here
(ADR-0004).
"""

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased

from app.settings import Settings

_configured = False


def configure_tracing(settings: Settings) -> None:
    """Install a tracer provider, if an endpoint is configured.

    Without an endpoint this is a no-op rather than an error: local development
    and the tests must not require a collector to be running, or every
    contributor needs one to start the app.
    """
    global _configured
    if _configured or not settings.otlp_endpoint:
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.version,
            "deployment.environment": settings.environment,
        }
    )

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
