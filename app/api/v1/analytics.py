from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.session import get_db
from app.models.notification import ChannelEnum, Notification
from app.schemas.common import Envelope

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/analytics/stats", response_model=Envelope[dict[str, Any]])
async def get_analytics_stats(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    channel: ChannelEnum | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Bonus: Get analytics grouped by status and channel."""
    stmt = select(
        Notification.channel,
        Notification.status,
        func.count(Notification.id).label("count")
    )
    
    if from_date:
        stmt = stmt.where(Notification.created_at >= from_date)
    if to_date:
        stmt = stmt.where(Notification.created_at <= to_date)
    if channel:
        stmt = stmt.where(Notification.channel == channel)
        
    stmt = stmt.group_by(Notification.channel, Notification.status)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Format output as nested dict: { "email": { "sent": 10, "failed": 2 }, ... }
    stats: dict[str, dict[str, int]] = {}
    for row in rows:
        ch = row.channel.value
        st = row.status.value
        cnt = row.count
        
        if ch not in stats:
            stats[ch] = {}
        stats[ch][st] = cnt

    return Envelope(data=stats)
