"""Structured logging.

Every log line is a JSON object carrying enough context to correlate it with a
metric and a trace: service, environment, level, timestamp, request id and — once
F8 lands OpenTelemetry — trace and span ids.

Redaction runs as a processor rather than at each call site, because "remember
not to log the token" is not a control. On a public repository the log pipeline
is the one place a secret can leak without tripping gitleaks.
"""

import logging
import re
from typing import Any, TextIO

import structlog
from structlog.typing import EventDict, WrappedLogger

from app.settings import Settings

# Substrings, not exact keys: `access_token`, `refresh_token` and
# `x_api_key` should all match without being enumerated.
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
    "cookie",
    "session_id",
)

_REDACTED = "[redacted]"
_EMAIL = re.compile(r"^([^@\s])[^@\s]*(@[^@\s]+\.[^@\s]+)$")


def redact_sensitive(
    _logger: WrappedLogger | None, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Drop secrets and mask email addresses before rendering."""
    for key, value in event_dict.items():
        lowered = key.lower()
        if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
            event_dict[key] = _REDACTED
        elif isinstance(value, str):
            # Emails are personal data rather than secrets: mask enough to keep
            # a log searchable by domain without storing the address itself.
            event_dict[key] = _EMAIL.sub(r"\1***\2", value)
    return event_dict


def _service_context(settings: Settings) -> Any:
    def processor(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", settings.service_name)
        event_dict.setdefault("env", settings.environment)
        return event_dict

    return processor


def configure_logging(settings: Settings, stream: TextIO | None = None) -> None:
    """Configure structlog and route stdlib logging through the same renderer.

    Third-party libraries (uvicorn above all) log via the standard library. If
    only structlog is configured, those records reach stdout as plain text and
    the log pipeline receives a mixture of JSON and prose — which means the
    startup and crash messages, exactly the ones worth reading during an
    incident, are the ones that fail to parse.

    `stream` exists so tests can assert on real rendered output.
    """
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )
    level = logging.getLevelNamesMapping()[settings.log_level]

    shared: list[Any] = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _service_context(settings),
        redact_sensitive,
    ]

    _configure_stdlib(shared, renderer, level, stream)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _service_context(settings),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_sensitive,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=(
            structlog.WriteLoggerFactory(file=stream)
            if stream is not None
            else structlog.PrintLoggerFactory()
        ),
        # Tests reconfigure between cases, so a cached logger would go stale.
        cache_logger_on_first_use=False,
    )


def _configure_stdlib(shared: list[Any], renderer: Any, level: int, stream: TextIO | None) -> None:
    """Render stdlib log records with the same processors and renderer."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]  # replace, so repeated configuration cannot duplicate
    root.setLevel(level)

    # Uvicorn installs its own handlers; clear them so records propagate to root
    # and are rendered once, in our format, rather than twice in two formats.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
