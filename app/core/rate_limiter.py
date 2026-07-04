import time
import uuid

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def check_rate_limit(user_id: str) -> tuple[bool, int]:
    """
    Sliding-window rate limiter using a Redis sorted set.
    Returns (allowed, remaining_requests).
    """
    redis = get_redis()
    key = f"rate_limit:{user_id}"
    now = time.time()
    window_start = now - settings.RATE_LIMIT_WINDOW_SECONDS
    request_id = str(uuid.uuid4())

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zadd(key, {request_id: now})
    pipe.zcard(key)
    pipe.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)
    results = await pipe.execute()

    count: int = results[2]
    allowed = count <= settings.RATE_LIMIT_REQUESTS
    remaining = max(0, settings.RATE_LIMIT_REQUESTS - count)

    if not allowed:
        # Remove the just-added entry since we're rejecting
        await redis.zrem(key, request_id)
        logger.warning("rate_limit_exceeded", user_id=user_id, count=count)

    return allowed, remaining
