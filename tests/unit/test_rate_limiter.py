"""
Rate limiter unit tests — mocks Redis pipeline to test boundary conditions.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_rate_limit_allows_100th_request():
    """The 100th request within the window should be allowed."""
    pipe_mock = AsyncMock()
    pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
    pipe_mock.__aexit__ = AsyncMock(return_value=False)
    # [removed_old, added, count=100, expire]
    pipe_mock.execute = AsyncMock(return_value=[0, 1, 100, 1])
    pipe_mock.zremrangebyscore = MagicMock()
    pipe_mock.zadd = MagicMock()
    pipe_mock.zcard = MagicMock()
    pipe_mock.expire = MagicMock()

    redis_mock = AsyncMock()
    redis_mock.pipeline = MagicMock(return_value=pipe_mock)

    with patch("app.core.rate_limiter._redis", redis_mock):
        from app.core.rate_limiter import check_rate_limit
        allowed, remaining = await check_rate_limit("user-1")

    assert allowed is True
    assert remaining == 0  # exactly at limit, 0 remaining


@pytest.mark.asyncio
async def test_rate_limit_rejects_101st_request():
    """The 101st request must be rejected with allowed=False."""
    pipe_mock = AsyncMock()
    pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
    pipe_mock.__aexit__ = AsyncMock(return_value=False)
    # count=101 → over limit
    pipe_mock.execute = AsyncMock(return_value=[0, 1, 101, 1])
    pipe_mock.zremrangebyscore = MagicMock()
    pipe_mock.zadd = MagicMock()
    pipe_mock.zcard = MagicMock()
    pipe_mock.expire = MagicMock()

    redis_mock = AsyncMock()
    redis_mock.pipeline = MagicMock(return_value=pipe_mock)
    redis_mock.zrem = AsyncMock()

    with patch("app.core.rate_limiter._redis", redis_mock):
        from app.core.rate_limiter import check_rate_limit
        allowed, remaining = await check_rate_limit("user-1")

    assert allowed is False
    assert remaining == 0
