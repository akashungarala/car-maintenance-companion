"""Typed application configuration.

Settings are read from the environment once, validated, and passed explicitly
into `create_app`. Deliberately not a module-level singleton reading os.environ
at import time: that makes configuration untestable and turns a misconfiguration
into a first-request failure rather than a startup failure.
"""

from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__

Environment = Literal["local", "test", "prod"]
LogFormat = Literal["json", "console"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CMC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "cmc-api"
    environment: Environment = "local"
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "console"
    version: str = __version__

    # Readiness checks are bounded so a hung dependency cannot hold the probe
    # open until the kubelet's own timeout fires.
    readiness_timeout_seconds: float = 2.0

    # Path prefix this service is served under when behind a proxy that strips
    # it — in production, akashungarala.com/apps/car-maintenance-companion/api.
    # FastAPI needs it to generate correct URLs for /docs and openapi.json;
    # without it the docs page loads and then fails to fetch its own schema.
    #
    # Empty locally and in tests, where the app is reached directly. Note this
    # changes only *generated* URLs, not the routes themselves, so Kubernetes
    # probes still hit /health and /ready on the pod unprefixed.
    root_path: str = ""

    @model_validator(mode="after")
    def _json_logs_in_production(self) -> Self:
        """Default to JSON logs in production unless explicitly overridden.

        Console output is far easier to read locally; Loki needs JSON. Rather
        than force every deployment to remember the flag, the environment
        implies it, while an explicit setting still wins.
        """
        if "log_format" not in self.model_fields_set and self.environment == "prod":
            self.log_format = "json"
        return self
