from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.notification import ChannelEnum
from app.models.user_preference import UserPreference


async def check_preference(session: AsyncSession, user_id: str, channel: ChannelEnum) -> bool:
    """
    Check if a user has opted in to a specific channel.
    Default behavior when no preference row exists: opted-in by default.
    """
    stmt = select(UserPreference).where(
        UserPreference.user_id == user_id, 
        UserPreference.channel == channel
    )
    result = await session.execute(stmt)
    pref = result.scalar_one_or_none()
    
    if pref is None:
        return True
    return pref.opted_in


async def get_all_preferences(session: AsyncSession, user_id: str) -> dict[str, bool]:
    """
    Returns all channel preferences for a user, filling in defaults (True) for missing ones.
    """
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    result = await session.execute(stmt)
    prefs = result.scalars().all()
    
    pref_dict = {p.channel.value: p.opted_in for p in prefs}
    
    # Fill defaults
    return {
        channel.value: pref_dict.get(channel.value, True) 
        for channel in ChannelEnum
    }


async def set_preference(
    session: AsyncSession, user_id: str, channel: ChannelEnum, opted_in: bool
) -> UserPreference:
    """Upsert a user preference."""
    stmt = select(UserPreference).where(
        UserPreference.user_id == user_id, 
        UserPreference.channel == channel
    )
    result = await session.execute(stmt)
    pref = result.scalar_one_or_none()
    
    if pref:
        pref.opted_in = opted_in
    else:
        pref = UserPreference(user_id=user_id, channel=channel, opted_in=opted_in)
        session.add(pref)
        
    await session.commit()
    await session.refresh(pref)
    return pref


async def enforce_preference(session: AsyncSession, user_id: str, channel: ChannelEnum) -> None:
    """
    Enforces preference. Raises ConflictError (409) if the user is opted out.
    """
    opted_in = await check_preference(session, user_id, channel)
    if not opted_in:
        # Returning a 409 Conflict as specified in the roadmap options (422 or 409)
        raise ConflictError(f"User {user_id} has opted out of {channel.value} notifications.")
