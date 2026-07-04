from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.idempotency_key import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, key: str) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(
        self,
        user_id: str,
        key: str,
        request_hash: str,
        response_status: int,
        response_body: dict,
    ) -> IdempotencyKey:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.IDEMPOTENCY_TTL_HOURS)
        record = IdempotencyKey(
            user_id=user_id,
            key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            expires_at=expires_at,
        )
        self._session.add(record)
        await self._session.commit()
        return record

    async def delete_expired(self) -> int:
        """Cleanup expired keys. Returns number of rows deleted."""
        now = datetime.now(timezone.utc)
        stmt = select(IdempotencyKey).where(IdempotencyKey.expires_at < now)
        result = await self._session.execute(stmt)
        expired = result.scalars().all()
        for record in expired:
            await self._session.delete(record)
        await self._session.commit()
        return len(expired)
