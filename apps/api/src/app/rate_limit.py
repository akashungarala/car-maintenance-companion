"""Redis-backed rate limiting.

A fixed window per client, incremented and expired atomically. The window is
crude compared to a sliding log -- a client can send its full budget at the end
of one window and again at the start of the next -- but it costs one Redis
round trip and one key, where a sliding log costs a sorted set per client and
grows with traffic. For limits whose purpose is to stop scripted abuse rather
than to meter billing, that trade is the right one.

Atomicity matters more than the algorithm here. INCR followed by EXPIRE as two
commands leaves a window where the process can die having created a counter
with no TTL, and that key locks its client out permanently. The script makes
the pair indivisible.
"""

from dataclasses import dataclass
from typing import Any

import structlog
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = structlog.get_logger()

KEY_PREFIX = "ratelimit:"

# Returns {count, ttl}. EXPIRE is set only on creation, so a burst cannot keep
# pushing the window forward and turn a one-minute limit into a rolling ban.
_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {current, redis.call('TTL', KEYS[1])}
"""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0
    remaining: int = 0
    #: False when Redis could not be reached. The request was allowed, but no
    #: limit was applied -- which is a different thing from being within budget,
    #: and the difference is what makes a silent outage visible.
    enforced: bool = True


class RateLimiter:
    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._script: Any = None

    async def check(self, key: str, *, limit: int, window_seconds: int) -> Decision:
        try:
            if self._script is None:
                self._script = self._redis.register_script(_SCRIPT)
            count, ttl = await self._script(keys=[f"{KEY_PREFIX}{key}"], args=[window_seconds])
        except (RedisConnectionError, RedisTimeoutError, RedisError, OSError) as exc:
            # Fail open, loudly. A limiter that rejects everything when Redis
            # blips turns a dependency outage into a full outage, and the abuse
            # it would have prevented is far cheaper than the downtime.
            logger.warning("rate_limit_unenforced", error=str(exc), key=key)
            return Decision(allowed=True, enforced=False)

        count = int(count)
        ttl = int(ttl)
        if count > limit:
            # TTL can read -1 briefly if the key is inspected between commands
            # on a replica; never return a Retry-After of zero or negative,
            # which tells a caller to retry immediately.
            return Decision(allowed=False, retry_after=max(ttl, 1))
        return Decision(allowed=True, remaining=max(limit - count, 0))
