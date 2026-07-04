import hashlib
import hmac
import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.webhook import Webhook, WebhookDelivery

logger = get_logger(__name__)


def _sign_payload(secret: str, payload: dict) -> str:
    """HMAC-SHA256 signature of the JSON payload, same pattern as GitHub webhooks."""
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def fire_webhooks(
    session: AsyncSession,
    user_id: str,
    event: str,
    payload: dict,
) -> None:
    """
    Find active webhooks subscribed to `event` for `user_id` and deliver the payload.
    Failures are recorded in webhook_deliveries but do NOT raise — fire-and-forget.
    """
    stmt = select(Webhook).where(
        Webhook.user_id == user_id,
        Webhook.active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    for webhook in webhooks:
        if event not in webhook.subscribed_events:
            continue

        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            payload=payload,
        )

        try:
            signature = _sign_payload(webhook.secret, payload)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    webhook.target_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Notification-Event": event,
                        "X-Hub-Signature-256": signature,
                    },
                )
            delivery.response_status = resp.status_code
            delivery.success = resp.is_success
            logger.info(
                "webhook_delivered",
                webhook_id=str(webhook.id),
                event=event,
                status=resp.status_code,
            )
        except Exception as exc:
            delivery.success = False
            delivery.response_status = None
            logger.warning("webhook_delivery_failed", webhook_id=str(webhook.id), error=str(exc))

        session.add(delivery)

    # Flush deliveries in one commit
    try:
        await session.commit()
    except Exception as exc:
        logger.error("webhook_delivery_commit_failed", error=str(exc))
        await session.rollback()
