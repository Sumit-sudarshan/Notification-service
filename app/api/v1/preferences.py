from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.preference import PreferenceResponse, PreferenceUpdate
from app.services.preference_service import get_all_preferences, set_preference

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/users/{user_id}/preferences", response_model=Envelope[list[PreferenceResponse]])
async def get_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    prefs_dict = await get_all_preferences(db, user_id)
    
    response_list = [
        PreferenceResponse(channel=channel, opted_in=opted_in)
        for channel, opted_in in prefs_dict.items()
    ]
    
    return Envelope(data=response_list)


@router.post("/users/{user_id}/preferences", response_model=Envelope[PreferenceResponse])
async def update_preference(
    user_id: str,
    preference_in: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    pref = await set_preference(
        db, 
        user_id=user_id, 
        channel=preference_in.channel, 
        opted_in=preference_in.opted_in
    )
    
    return Envelope(data=PreferenceResponse.model_validate(pref))
