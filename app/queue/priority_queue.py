"""
Redis-backed priority queue using a single sorted set.

Score formula: (4 - priority_weight) * 1e13 + unix_timestamp_ms
  - critical (weight=4): score starts at 0 + ts  → ZPOPMIN returns these first
  - high     (weight=3): score starts at 1e13 + ts
  - normal   (weight=2): score starts at 2e13 + ts
  - low      (weight=1): score starts at 3e13 + ts

Within the same priority tier, older items (lower timestamp) have lower scores
and are therefore dequeued first — giving FIFO ordering within each tier.

ZPOPMIN is atomic — safe for multiple concurrent worker processes (no Lua needed).
"""

import time
from uuid import UUID

import redis.asyncio as aioredis

from app.core.logging import get_logger

logger = get_logger(__name__)

QUEUE_KEY = "notification:queue"

PRIORITY_WEIGHTS: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
}


def _score(priority: str, timestamp_ms: float | None = None) -> float:
    weight = PRIORITY_WEIGHTS.get(priority, 2)
    ts = timestamp_ms if timestamp_ms is not None else time.time() * 1000
    return (4 - weight) * 1e13 + ts


class PriorityQueue:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def enqueue(self, notification_id: UUID, priority: str) -> None:
        """Add a notification to the queue. Score encodes priority + arrival time."""
        score = _score(priority)
        member = str(notification_id)
        await self._redis.zadd(QUEUE_KEY, {member: score})
        logger.info("enqueued", notification_id=member, priority=priority, score=score)

    async def enqueue_delayed(
        self, notification_id: UUID, priority: str, delay_seconds: float
    ) -> None:
        """Re-enqueue with a future timestamp (for retries with backoff)."""
        future_ts_ms = (time.time() + delay_seconds) * 1000
        score = _score(priority, timestamp_ms=future_ts_ms)
        member = str(notification_id)
        await self._redis.zadd(QUEUE_KEY, {member: score})
        logger.info(
            "enqueued_delayed",
            notification_id=member,
            priority=priority,
            delay_seconds=delay_seconds,
            score=score,
        )

    async def dequeue(self) -> str | None:
        """
        Atomically pop the highest-priority, oldest item whose score ≤ now
        (i.e. not a future-scheduled retry item).

        Returns notification_id string or None if queue is empty / no due items.
        """
        now_ms = time.time() * 1000

        # Use ZRANGEBYSCORE to peek at due items, then ZPOPMIN only if it's due.
        # We do this via a Lua script to keep it atomic.
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        -- Get the member with the lowest score
        local result = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        if #result == 0 then
            return nil
        end
        local member = result[1]
        local score = tonumber(result[2])
        -- Only pop if it's due (score ≤ now for current items, or always for non-delayed)
        -- Items within the first priority tier (0..1e13) are always due.
        -- Delayed retry items have ts component set to a future time.
        -- We compare just the timestamp portion.
        local ts_component = score % 1e13
        if ts_component <= now then
            redis.call('ZREM', key, member)
            return member
        end
        return nil
        """
        result = await self._redis.eval(lua_script, 1, QUEUE_KEY, now_ms)
        return result  # type: ignore[return-value]

    async def depth(self) -> int:
        """Return total number of items in the queue (including future-scheduled)."""
        return await self._redis.zcard(QUEUE_KEY)

    async def due_depth(self) -> int:
        """Return count of items due right now (score ts component ≤ now)."""
        now_ms = time.time() * 1000
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local all = redis.call('ZRANGE', key, 0, -1, 'WITHSCORES')
        local count = 0
        for i = 1, #all, 2 do
            local score = tonumber(all[i+1])
            local ts = score % 1e13
            if ts <= now then
                count = count + 1
            end
        end
        return count
        """
        return await self._redis.eval(lua_script, 1, QUEUE_KEY, now_ms)  # type: ignore[return-value]
