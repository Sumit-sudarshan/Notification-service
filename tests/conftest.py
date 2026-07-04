"""
Test configuration.

- Unit tests in tests/unit/ mock everything at the service level — no DB/Redis needed.
- Integration tests in tests/integration/ use the real FastAPI app but mock the DB session
  and Redis connection via dependency overrides. This lets them run without any external services.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


# ─── Override DB dependency ───────────────────────────────────────────────────

def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None), scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=0)
    return session


@pytest_asyncio.fixture
async def mock_db():
    return _mock_session()


# ─── Override Redis (rate limiter + metrics) ──────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def mock_redis(monkeypatch):
    """Auto-used fixture that patches Redis so no real Redis is needed."""
    redis_mock = AsyncMock()
    redis_mock.zremrangebyscore = AsyncMock()
    redis_mock.zadd = AsyncMock()
    redis_mock.zcard = AsyncMock(return_value=0)
    redis_mock.expire = AsyncMock()
    redis_mock.zrem = AsyncMock()
    redis_mock.incrby = AsyncMock()
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.mget = AsyncMock(return_value=[])
    # pipeline mock
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[0, 0, 0, 0])  # [removed, added, count, expire]
    redis_mock.pipeline = MagicMock(return_value=pipe)

    import app.core.rate_limiter as rl
    monkeypatch.setattr(rl, "_redis", redis_mock)
    return redis_mock


# ─── HTTP test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─── Authenticated client ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": settings.API_KEY},
    ) as c:
        yield c

