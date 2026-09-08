"""Request correlation and the access log.

Binds a request id into structlog's context so every log line emitted while
handling a request carries it, without threading an argument through every
function. F8 extends the same binding with trace and span ids.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

REQUEST_ID_HEADER = "X-Request-ID"

# Logged in place of the path when no route matched. A raw 404 path is
# attacker-controlled and unbounded; metrics label on this field, so letting
# raw paths through would exhaust the active-series budget (ADR-0004).
UNMATCHED_ROUTE = "__unmatched__"

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            logger.exception("unhandled_exception")
            response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.info(
                "http_request",
                request_id=request_id,
                method=request.method,
                route=_route_template(request),
                path=request.url.path,
                status=status,
                duration_ms=duration_ms,
            )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _route_template(request: Request) -> str:
    """The matched route pattern (`/vehicles/{id}`), never the raw path."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else UNMATCHED_ROUTE
