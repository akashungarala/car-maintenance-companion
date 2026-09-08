"""Typed configuration.

Settings are read from the environment once, validated, and passed explicitly
into `create_app`. No module-level singleton reading os.environ at import time:
that makes configuration untestable and hides failures until first request.
"""

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_defaults_are_safe_for_local_development() -> None:
    settings = Settings()

    assert settings.service_name == "cmc-api"
    assert settings.environment == "local"
    assert settings.log_format == "console"


def test_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMC_ENVIRONMENT", "prod")
    monkeypatch.setenv("CMC_LOG_LEVEL", "WARNING")

    settings = Settings()

    assert settings.environment == "prod"
    assert settings.log_level == "WARNING"


def test_rejects_an_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="staging-ish")


def test_production_defaults_to_json_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMC_ENVIRONMENT", "prod")

    assert Settings().log_format == "json"
