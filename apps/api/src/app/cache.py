"""Redis connectivity.

Redis backs the job queue and, from F9, rate limiting. An instance that cannot
reach it can still serve reads but cannot enqueue work or enforce a limit, so
it belongs out of the Service endpoints rather than half-serving traffic.

Readiness only. Liveness must never depend on Redis: a blip would restart every
pod at once and turn a recoverable outage into a crash loop.
"""

from typing import Any

import structlog
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = structlog.get_logger()


class RedisHealth:
    """Wraps a Redis client with a health check that hides only outages."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def is_healthy(self) -> bool:
        try:
            return bool(await self._client.ping())
        # Connectivity only. Catching everything would turn a programming error
        # into "Redis is down", which is both wrong and much harder to find.
        # Builtin ConnectionError is an OSError, so this covers both families.
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            logger.warning("redis_unreachable", error=str(exc))
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def build_client(url: str) -> Any:
    """A client that fails fast rather than hanging a probe.

    The readiness registry already bounds each check, but a client with no
    timeout can leave a connection open well past that, so slow failures
    accumulate sockets while the probe reports a clean timeout.
    """
    import redis.asyncio as redis

    # redis-py ships type hints but leaves from_url untyped, so strict mode
    # rejects the call rather than the arguments. Narrowed to this one line.
    return redis.from_url(  # type: ignore[no-untyped-call]
        url,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
        health_check_interval=30,
    )
