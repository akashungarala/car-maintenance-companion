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


def test_root_path_is_empty_by_default() -> None:
    """Local and test runs reach the app directly, with no proxy prefix."""
    assert Settings().root_path == ""


def test_root_path_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMC_ROOT_PATH", "/apps/car-maintenance-companion/api")

    assert Settings().root_path == "/apps/car-maintenance-companion/api"


def test_database_url_is_normalised_to_the_async_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CloudNativePG generates a plain postgresql:// URI.

    Accepting it as-is means the operator's own secret can be consumed without
    string surgery in YAML — and a bare postgresql:// URL would otherwise pick
    the sync driver, which is not installed, and fail at first connection
    rather than at startup.
    """
    monkeypatch.setenv("CMC_DATABASE_URL", "postgresql://u:p@cmc-db-rw:5432/cmc")

    assert Settings().database_url == "postgresql+asyncpg://u:p@cmc-db-rw:5432/cmc"


def test_an_explicit_async_url_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMC_DATABASE_URL", "postgresql+asyncpg://u:p@host/db")

    assert Settings().database_url == "postgresql+asyncpg://u:p@host/db"


def test_redis_url_is_unset_by_default() -> None:
    assert Settings().redis_url is None


def test_redis_url_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMC_REDIS_URL", "redis://cmc-redis:6379/0")

    assert Settings().redis_url == "redis://cmc-redis:6379/0"
