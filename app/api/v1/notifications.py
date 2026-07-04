import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.logging import get_logger
from app.core.rate_limiter import check_rate_limit
from app.core.security import require_api_key
from app.db.session import get_db
from app.models.notification import ChannelEnum, Notification, PriorityEnum, StatusEnum
from app.queue.priority_queue import PriorityQueue
from app.core.rate_limiter import get_redis
from app.schemas.common import Envelope, PaginatedResponse
from app.schemas.notification import NotificationCreate, NotificationDetailResponse, NotificationResponse
from app.services.idempotency_service import check_idempotency, generate_request_hash, save_idempotency_key
from app.services.preference_service import enforce_preference
from app.services.template_service import render_template
from pydantic import BaseModel
from app.core.metrics import inc_metric
logger = get_logger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


def get_queue() -> PriorityQueue:
    return PriorityQueue(get_redis())


@router.post("/notifications", response_model=Envelope[NotificationResponse], status_code=201)
async def create_notification(
    request: Request,
    response: Response,
    notification_in: NotificationCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    queue: PriorityQueue = Depends(get_queue),
) -> Any:
    # 1. Rate Limiting
    allowed, remaining = await check_rate_limit(notification_in.user_id)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        raise RateLimitError(retry_after=settings.RATE_LIMIT_WINDOW_SECONDS)

    # 2. Idempotency Check
    req_hash = ""
    if idempotency_key:
        body_bytes = await request.body()
        # Parse body again to ensure consistent hashing
        import json
        try:
            body_dict = json.loads(body_bytes)
        except json.JSONDecodeError:
            body_dict = notification_in.model_dump(mode="json")
            
        req_hash = generate_request_hash(body_dict)
        is_found, cached_resp, cached_status = await check_idempotency(
            db, notification_in.user_id, idempotency_key, req_hash
        )
        if is_found:
            logger.info("idempotent_replay", user_id=notification_in.user_id, key=idempotency_key)
            response.status_code = cached_status or 201
            return cached_resp

    # 3. Preference Enforcement
    await enforce_preference(db, notification_in.user_id, notification_in.channel)

    # 4. Template Rendering / Validation
    payload = await render_template(
        db,
        variables=notification_in.template_variables,
        template_id=notification_in.template_id,
        inline_body=notification_in.message,
        inline_subject=notification_in.subject,
    )

    # 5. Persist Notification (pending -> queued)
    correlation_id = request.headers.get("X-Correlation-ID")
    notification = Notification(
        user_id=notification_in.user_id,
        channel=notification_in.channel,
        priority=notification_in.priority,
        status=StatusEnum.queued,
        template_id=notification_in.template_id,
        payload=payload,
        idempotency_key=idempotency_key,
        max_retries=settings.MAX_RETRIES,
        scheduled_at=notification_in.scheduled_at,
        correlation_id=correlation_id,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # 6. Enqueue
    await queue.enqueue(notification.id, notification.priority.value)
    await inc_metric("notifications_enqueued_total", {"channel": notification.channel.value})
    logger.info("notification_enqueued", notification_id=str(notification.id))

    # 7. Save Idempotency Key
    resp_data = Envelope(data=NotificationResponse.model_validate(notification)).model_dump(mode="json")
    if idempotency_key:
        await save_idempotency_key(
            db, notification_in.user_id, idempotency_key, req_hash, 201, resp_data
        )

    return resp_data


@router.get("/notifications/{notification_id}", response_model=Envelope[NotificationDetailResponse])
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = (
        select(Notification)
        .options(selectinload(Notification.attempts))
        .where(Notification.id == notification_id)
    )
    result = await db.execute(stmt)
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundError(f"Notification {notification_id} not found")

    return Envelope(data=NotificationDetailResponse.model_validate(notification))


@router.get("/users/{user_id}/notifications", response_model=PaginatedResponse[NotificationResponse])
async def list_user_notifications(
    user_id: str,
    channel: ChannelEnum | None = None,
    status: StatusEnum | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    # Build query
    stmt = select(Notification).where(Notification.user_id == user_id)
    if channel:
        stmt = stmt.where(Notification.channel == channel)
    if status:
        stmt = stmt.where(Notification.status == status)
        
    stmt = stmt.order_by(Notification.created_at.desc())

    # Get total count (for pagination) - simplistic approach
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    # Execute paginated query
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    return PaginatedResponse(
        data=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        limit=limit,
        offset=offset,
    )

class BatchItemResponse(BaseModel):
    success: bool
    data: NotificationResponse | None = None
    error: str | None = None

@router.post("/notifications/batch", response_model=Envelope[list[BatchItemResponse]], status_code=207)
async def create_notification_batch(
    request: Request,
    response: Response,
    notifications_in: list[NotificationCreate],
    db: AsyncSession = Depends(get_db),
    queue: PriorityQueue = Depends(get_queue),
) -> Any:
    """Bonus: Batch endpoint. Returns 207 Multi-Status with per-item success/failure."""
    results = []
    correlation_id = request.headers.get("X-Correlation-ID")

    for notif_in in notifications_in:
        try:
            # Rate Limiting per user inside batch
            allowed, _ = await check_rate_limit(notif_in.user_id)
            if not allowed:
                results.append(BatchItemResponse(success=False, error="Rate limit exceeded"))
                continue

            # Preference Enforcement
            await enforce_preference(db, notif_in.user_id, notif_in.channel)

            # Template Rendering
            payload = await render_template(
                db,
                variables=notif_in.template_variables,
                template_id=notif_in.template_id,
                inline_body=notif_in.message,
                inline_subject=notif_in.subject,
            )

            # Persist
            notification = Notification(
                user_id=notif_in.user_id,
                channel=notif_in.channel,
                priority=notif_in.priority,
                status=StatusEnum.queued,
                template_id=notif_in.template_id,
                payload=payload,
                max_retries=settings.MAX_RETRIES,
                scheduled_at=notif_in.scheduled_at,
                correlation_id=correlation_id,
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            # Enqueue
            await queue.enqueue(notification.id, notification.priority.value)
            await inc_metric("notifications_enqueued_total", {"channel": notification.channel.value})
            
            results.append(BatchItemResponse(
                success=True, 
                data=NotificationResponse.model_validate(notification)
            ))
            
        except Exception as e:
            await db.rollback()
            results.append(BatchItemResponse(success=False, error=str(e)))

    if any(not r.success for r in results):
        response.status_code = 207

    return Envelope(data=results)

