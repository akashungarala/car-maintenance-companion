"""Tracing, and the log/trace correlation that makes it useful.

A trace nobody can reach from a log line is decoration. The point of F8 is that
one request produces a metric, a log carrying its trace_id, and a trace those
link to — so these tests target the joins, not the SDK.
"""

import io
import json

import structlog
from opentelemetry import trace

from app.logging import configure_logging
from app.settings import Settings
from app.telemetry import configure_tracing, inject_trace_context, restore_trace_context


def test_tracing_is_a_no_op_when_unconfigured() -> None:
    """Phase 0 ran with no exporter, and local development still does.

    Instrumentation must never require a collector to be present, or every
    developer needs one running to start the app.
    """
    settings = Settings(environment="test")

    configure_tracing(settings)  # must not raise

    assert settings.otlp_endpoint is None


def test_log_lines_carry_trace_and_span_ids_when_a_span_is_active() -> None:
    """This is the join. Without it a log line cannot be traced back."""
    buffer = io.StringIO()
    configure_logging(Settings(environment="test", log_format="json"), stream=buffer)
    configure_tracing(Settings(environment="test", otlp_endpoint="http://localhost:4318"))

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("unit-of-work"):
        structlog.get_logger().info("something_happened")

    line = json.loads(buffer.getvalue())
    assert line["trace_id"] != ""
    assert line["span_id"] != ""
    # 128-bit trace id, 64-bit span id, rendered as hex.
    assert len(line["trace_id"]) == 32
    assert len(line["span_id"]) == 16


def test_log_lines_omit_trace_ids_outside_a_span() -> None:
    """Empty strings would look like a broken trace rather than no trace."""
    buffer = io.StringIO()
    configure_logging(Settings(environment="test", log_format="json"), stream=buffer)

    structlog.get_logger().info("outside_any_span")

    line = json.loads(buffer.getvalue())
    assert "trace_id" not in line


def test_trace_context_survives_the_queue() -> None:
    """An async job must join the trace that enqueued it.

    Without propagation the enqueue and the execution are two unrelated traces,
    and "why was this job slow" cannot be answered from the request that caused
    it — which is exactly the question a queue makes hard.
    """
    configure_tracing(Settings(environment="test", otlp_endpoint="http://localhost:4318"))
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("enqueue") as span:
        expected = format(span.get_span_context().trace_id, "032x")
        carrier = inject_trace_context({})

    assert "traceparent" in carrier, "nothing to propagate"

    ctx = restore_trace_context(carrier)
    restored = trace.get_current_span(ctx).get_span_context()

    assert format(restored.trace_id, "032x") == expected


def test_restoring_an_empty_carrier_is_safe() -> None:
    """Jobs enqueued before this shipped, or by hand, have no context."""
    ctx = restore_trace_context({})

    assert trace.get_current_span(ctx).get_span_context().trace_id == 0
