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

    #: Requests per minute per caller for ordinary API traffic.
    rate_limit_per_minute: int = 100
    #: Authentication is far stricter: it is the endpoint worth guessing
    #: against, and a legitimate person signs in once, not five times a minute.
    auth_rate_limit_per_minute: int = 5
    #: An escape hatch for an incident, not a feature flag. Turning limits off
    #: is a decision someone should have to make deliberately.
    rate_limit_enabled: bool = True

    # Path prefix this service is served under when behind a proxy that strips
    # it — in production, akashungarala.com/apps/car-maintenance-companion/api.
    # FastAPI needs it to generate correct URLs for /docs and openapi.json;
    # without it the docs page loads and then fails to fetch its own schema.
    #
    # Empty locally and in tests, where the app is reached directly. Note this
    # changes only *generated* URLs, not the routes themselves, so Kubernetes
    # probes still hit /health and /ready on the pod unprefixed.
    root_path: str = ""

    #: Where the magic link points. The API does not know the browser's URL --
    #: it is reached through Cloudflare, Traefik and a path prefix -- so a link
    #: built from the request would point somewhere unreachable.
    app_base_url: str = "http://localhost:3000"

    #: Sending-only, scoped to the sending domain. Absent in local development
    #: and in tests, where the link is logged instead of sent -- so nobody needs
    #: a credential to work on sign-in.
    resend_api_key: str | None = None
    email_from: str = "Car Maintenance Companion <garage@send.akashungarala.com>"

    # Unset in Phase 0 and in most tests: the service ran without a database at
    # all, and must keep being able to. When set, a readiness check is
    # registered for it — but never a liveness check.
    database_url: str | None = None

    # Also unset in Phase 0. Redis backs the job queue, and later the cache and
    # rate limiter — three concrete uses, not one component looking for a job.
    redis_url: str | None = None

    # OTLP endpoint of the local Collector, never a vendor URL (ADR-0004).
    # Unset means tracing is off, which is the correct default for local
    # development and tests.
    otlp_endpoint: str | None = None

    # 1.0 while traffic is negligible: sampling away traces on a system with no
    # load just makes debugging harder for no saving. Revisit against the
    # 50 GB trace allowance if volume ever justifies it.
    trace_sample_ratio: float = 1.0

    @model_validator(mode="after")
    def _normalise_database_driver(self) -> Self:
        """Accept CloudNativePG's plain postgresql:// URI.

        The operator generates the connection secret itself, so taking its
        format verbatim avoids rewriting it in YAML. A bare postgresql:// URL
        selects SQLAlchemy's sync driver, which is not installed — that would
        fail at first connection rather than at startup, which is a much worse
        place to find out.
        """
        if self.database_url and self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self

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
