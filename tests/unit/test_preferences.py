import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import ConflictError
from app.models.notification import ChannelEnum
from app.services.preference_service import check_preference, enforce_preference

@pytest.mark.asyncio
async def test_check_preference_default_opt_in():
    session = AsyncMock()
    # Mocking result.scalar_one_or_none() to return None (no row exists)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    result = await check_preference(session, "user1", ChannelEnum.email)
    assert result is True

@pytest.mark.asyncio
async def test_check_preference_opted_out():
    session = AsyncMock()
    mock_pref = MagicMock()
    mock_pref.opted_in = False
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_pref
    session.execute.return_value = mock_result
    
    result = await check_preference(session, "user1", ChannelEnum.email)
    assert result is False

@pytest.mark.asyncio
async def test_enforce_preference_raises_conflict():
    session = AsyncMock()
    mock_pref = MagicMock()
    mock_pref.opted_in = False
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_pref
    session.execute.return_value = mock_result
    
    with pytest.raises(ConflictError, match="has opted out of email"):
        await enforce_preference(session, "user1", ChannelEnum.email)
