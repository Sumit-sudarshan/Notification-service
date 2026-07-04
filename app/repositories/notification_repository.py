"""
Repository layer — thin DB access classes, one per model.
Services call these instead of writing SQLAlchemy queries inline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import ChannelEnum, Notification, StatusEnum


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        stmt = (
            select(Notification)
            .options(selectinload(Notification.attempts))
            .where(Notification.id == notification_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        channel: ChannelEnum | None = None,
        status: StatusEnum | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        from sqlalchemy import func

        stmt = select(Notification).where(Notification.user_id == user_id)
        if channel:
            stmt = stmt.where(Notification.channel == channel)
        if status:
            stmt = stmt.where(Notification.status == status)
        stmt = stmt.order_by(Notification.created_at.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self._session.scalar(count_stmt) or 0

        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def save(self, notification: Notification) -> Notification:
        self._session.add(notification)
        await self._session.commit()
        await self._session.refresh(notification)
        return notification
