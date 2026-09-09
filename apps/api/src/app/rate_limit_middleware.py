"""Applying rate limits to requests."""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app import metrics as app_metrics
from app.rate_limit import RateLimiter
from app.settings import Settings

logger = structlog.get_logger()

# Kubernetes probes these every few seconds, forever, from one address.
# Limiting them would fail readiness, remove the pod from the Service, then
# fail liveness and restart it -- the rate limiter causing precisely the outage
# it exists to prevent, across every pod simultaneously.
EXEMPT_PATHS = frozenset({"/health", "/ready"})

# No auth routes exist in Phase 0. The bucket is defined now so that adding
# sign-in in E1-001 is covered by a limit that already works, rather than one
# written under time pressure on the endpoint most worth attacking.
AUTH_PREFIXES = ("/auth",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Callable[..., object], *, limiter: RateLimiter, settings: Settings):
        super().__init__(app)  # type: ignore[arg-type]
        self._limiter = limiter
        self._settings = settings

    def _identity(self, request: Request) -> str:
        """Who is being limited.

        CF-Connecting-IP is set by Cloudflare and overwrites anything the
        client sends, so it is the one header here that a caller cannot forge
        -- provided the origin only accepts connections from Cloudflare, which
        is enforced separately by the ingress firewall rules. Without that
        restriction this header is a suggestion, not a fact.

        The peer address is a poor fallback: behind Traefik it is a pod IP, so
        every caller shares one bucket and a per-client limit silently becomes
        a global one. It is still better than no limit.
        """
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded.strip()
        client = request.client
        return client.host if client else "unknown"

    def _bucket(self, path: str) -> tuple[str, int]:
        if path.startswith(AUTH_PREFIXES):
            return "auth", self._settings.auth_rate_limit_per_minute
        return "api", self._settings.rate_limit_per_minute

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.scope.get("path", "")
        if not self._settings.rate_limit_enabled or path.rstrip("/") in EXEMPT_PATHS:
            return await call_next(request)

        bucket, limit = self._bucket(path)
        identity = self._identity(request)
        decision = await self._limiter.check(f"{bucket}:{identity}", limit=limit, window_seconds=60)

        if not decision.allowed:
            app_metrics.record_rate_limit_rejection(bucket)
            # The address goes in the log, never in a metric label.
            logger.warning(
                "rate_limited", bucket=bucket, client=identity, retry_after=decision.retry_after
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(decision.retry_after)},
            )

        return await call_next(request)
