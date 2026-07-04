from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import ChannelEnum
from app.models.user_preference import UserPreference


class PreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, channel: ChannelEnum) -> UserPreference | None:
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.channel == channel,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, user_id: str) -> list[UserPreference]:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, user_id: str, channel: ChannelEnum, opted_in: bool) -> UserPreference:
        pref = await self.get(user_id, channel)
        if pref:
            pref.opted_in = opted_in
        else:
            pref = UserPreference(user_id=user_id, channel=channel, opted_in=opted_in)
            self._session.add(pref)
        await self._session.commit()
        await self._session.refresh(pref)
        return pref
