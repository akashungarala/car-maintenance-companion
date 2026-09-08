"""Structured logging and redaction.

Two separable concerns:
  * the *shape* of a log line — it must be JSON and carry the fields needed to
    correlate a log with a metric and a trace;
  * redaction — secrets must never reach the log pipeline, because on a public
    project the logs are the one place a secret can leak without tripping
    gitleaks.
"""

import io
import json
from typing import Any

import structlog

from app.logging import configure_logging, redact_sensitive
from app.settings import Settings


def _emit_and_parse(settings: Settings, **fields: Any) -> dict[str, Any]:
    buffer = io.StringIO()
    configure_logging(settings, stream=buffer)
    structlog.get_logger().info("http_request", **fields)
    return json.loads(buffer.getvalue())


def test_log_line_is_json_with_required_fields() -> None:
    settings = Settings(environment="test", log_format="json")

    line = _emit_and_parse(
        settings,
        request_id="req-1",
        method="GET",
        route="/health",
        status=200,
        duration_ms=1.5,
    )

    for field in (
        "timestamp",
        "service",
        "env",
        "level",
        "request_id",
        "method",
        "route",
        "status",
        "duration_ms",
    ):
        assert field in line, f"missing required log field: {field}"


def test_log_line_carries_service_and_environment() -> None:
    settings = Settings(environment="test", log_format="json")

    line = _emit_and_parse(settings)

    assert line["service"] == "cmc-api"
    assert line["env"] == "test"


def test_redacts_authorization_header() -> None:
    event = redact_sensitive(None, "info", {"authorization": "Bearer sk-abc123"})

    assert event["authorization"] == "[redacted]"


def test_redacts_token_and_secret_keys() -> None:
    event = redact_sensitive(
        None,
        "info",
        {
            "access_token": "abc",
            "refresh_token": "def",
            "password": "hunter2",
            "api_key": "k",
            "client_secret": "s",
        },
    )

    assert set(event.values()) == {"[redacted]"}


def test_masks_email_addresses() -> None:
    event = redact_sensitive(None, "info", {"user_email": "akash@example.com"})

    assert event["user_email"] == "a***@example.com"
    assert "akash@example.com" not in json.dumps(event)


def test_redaction_is_case_insensitive() -> None:
    event = redact_sensitive(None, "info", {"Authorization": "Bearer x", "API_KEY": "y"})

    assert event["Authorization"] == "[redacted]"
    assert event["API_KEY"] == "[redacted]"


def test_redaction_leaves_ordinary_fields_alone() -> None:
    event = redact_sensitive(None, "info", {"route": "/vehicles/{id}", "status": 200})

    assert event == {"route": "/vehicles/{id}", "status": 200}


def test_stdlib_logs_are_rendered_as_json_too() -> None:
    """Uvicorn's startup and error records must parse like everything else."""
    import logging

    settings = Settings(environment="test", log_format="json")
    buffer = io.StringIO()
    configure_logging(settings, stream=buffer)

    logging.getLogger("uvicorn.error").info("Application startup complete.")

    line = json.loads(buffer.getvalue())
    assert line["event"] == "Application startup complete."
    assert line["service"] == "cmc-api"
    assert line["env"] == "test"
    assert line["level"] == "info"


def test_repeated_configuration_does_not_duplicate_handlers() -> None:
    import logging

    settings = Settings(environment="test", log_format="json")
    configure_logging(settings, stream=io.StringIO())
    configure_logging(settings, stream=io.StringIO())

    assert len(logging.getLogger().handlers) == 1
