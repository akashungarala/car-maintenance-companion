"""Liveness and readiness.

These answer different questions and must not be conflated:

  /health   Is this process alive? If it fails, Kubernetes **restarts** the
            container. It therefore touches nothing external — a brief database
            blip must not turn into a cluster-wide restart storm.

  /ready    Can this instance serve traffic? If it fails, Kubernetes removes the
            pod from the Service endpoints but leaves it running. It therefore
            *does* check dependencies.

The registry is empty in F2 by design: F6 registers the database check and F7
registers Redis. The contract is proven before either exists.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.utils import suppress_instrumentation

CheckFn = Callable[[], Awaitable[bool]]

logger = structlog.get_logger()


@dataclass(frozen=True)
class CheckResult:
    healthy: bool
    detail: str | None = None


class ReadinessRegistry:
    """Named dependency checks, run concurrently and bounded by a timeout."""

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self._checks: dict[str, CheckFn] = {}
        self._timeout = timeout_seconds

    def register(self, name: str, check: CheckFn) -> None:
        self._checks[name] = check

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._checks)

    async def _run_one(self, name: str, check: CheckFn) -> CheckResult:
        # Probe traffic must not generate spans. `/ready` is already excluded
        # from HTTP instrumentation, but that only suppresses the server span:
        # the database check inside still emitted SQLAlchemy spans, and with no
        # HTTP span to parent them they arrived as orphan roots. Measured at 48
        # spans/minute in production -- two per probe, every five seconds,
        # across two replicas -- drowning real traces in probe noise.
        #
        # Suppression is contextvar-based, and asyncio.wait_for copies the
        # current context into the task it creates, so it reaches the check.
        try:
            with suppress_instrumentation():
                healthy = await asyncio.wait_for(check(), timeout=self._timeout)
        except TimeoutError:
            # A hung dependency must not hold the probe open until the kubelet's
            # own timeout fires — that reads as a probe failure with no reason.
            return CheckResult(False, f"check timed out after {self._timeout}s")
        except Exception as exc:  # any failure to answer means "not ready"
            logger.warning("readiness_check_failed", check=name, error=str(exc))
            return CheckResult(False, str(exc))
        return CheckResult(bool(healthy))

    async def run_all(self) -> dict[str, CheckResult]:
        if not self._checks:
            return {}
        names = list(self._checks)
        results = await asyncio.gather(*(self._run_one(name, self._checks[name]) for name in names))
        return dict(zip(names, results, strict=True))


router = APIRouter(tags=["operations"])


@router.get("/health", summary="Liveness probe")
async def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }


@router.get("/ready", summary="Readiness probe")
async def ready(request: Request) -> JSONResponse:
    registry: ReadinessRegistry = request.app.state.readiness
    results = await registry.run_all()
    is_ready = all(result.healthy for result in results.values())

    body: dict[str, Any] = {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            name: {"healthy": result.healthy, "detail": result.detail}
            for name, result in results.items()
        },
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=body)
