from typing import Any
from pydantic import BaseModel
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.session import get_db
from app.models.webhook import Webhook
from app.schemas.common import Envelope
from app.core.exceptions import NotFoundError

router = APIRouter(dependencies=[Depends(require_api_key)])


class WebhookCreate(BaseModel):
    user_id: str
    target_url: str
    secret: str
    subscribed_events: list[str]


class WebhookResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    target_url: str
    subscribed_events: list[str]
    active: bool

    model_config = {"from_attributes": True}


@router.post("/webhooks", response_model=Envelope[WebhookResponse], status_code=201)
async def create_webhook(
    webhook_in: WebhookCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Bonus: Register a webhook."""
    webhook = Webhook(
        user_id=webhook_in.user_id,
        target_url=webhook_in.target_url,
        secret=webhook_in.secret,
        subscribed_events=webhook_in.subscribed_events,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return Envelope(data=WebhookResponse.model_validate(webhook))


@router.get("/webhooks", response_model=Envelope[list[WebhookResponse]])
async def list_webhooks(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Bonus: List webhooks."""
    stmt = select(Webhook)
    if user_id:
        stmt = stmt.where(Webhook.user_id == user_id)
        
    result = await db.execute(stmt)
    webhooks = result.scalars().all()
    
    return Envelope(data=[WebhookResponse.model_validate(w) for w in webhooks])


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Bonus: Delete a webhook."""
    stmt = select(Webhook).where(Webhook.id == webhook_id)
    result = await db.execute(stmt)
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise NotFoundError("Webhook not found")
        
    await db.delete(webhook)
    await db.commit()
