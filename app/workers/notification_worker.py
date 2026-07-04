import asyncio
import signal
import sys
from typing import Any
from uuid import UUID

import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limiter import get_redis
from app.core.metrics import inc_metric
from app.db.session import AsyncSessionLocal
from app.models.notification import Notification, StatusEnum
from app.models.notification_attempt import AttemptStatusEnum, NotificationAttempt
from app.providers.mock_providers import get_provider
from app.queue.priority_queue import PriorityQueue
from app.services.webhook_service import fire_webhooks
from app.workers.retry_scheduler import calculate_backoff_delay, should_retry

setup_logging()
logger = structlog.get_logger(__name__)


class Worker:
    def __init__(self) -> None:
        self.redis = get_redis()
        self.queue = PriorityQueue(self.redis)
        self.running = False

    async def process_notification(self, notification_id_str: str) -> None:
        try:
            notification_id = UUID(notification_id_str)
        except ValueError:
            logger.error("invalid_notification_id", notification_id=notification_id_str)
            return

        async with AsyncSessionLocal() as session:
            # 1. Fetch notification
            notification = await session.get(Notification, notification_id)
            if not notification:
                logger.error("notification_not_found", notification_id=notification_id_str)
                return

            if notification.correlation_id:
                structlog.contextvars.bind_contextvars(correlation_id=notification.correlation_id)

            # 2. Mark processing (at-least-once semantics)
            notification.status = StatusEnum.processing
            await session.commit()
            logger.info("processing_notification", notification_id=notification_id_str, channel=notification.channel.value)

            # 3. Call provider
            try:
                provider = get_provider(notification.channel.value)
                result = await provider.send(notification)
            except Exception as e:
                logger.exception("provider_exception", error=str(e))
                from app.providers.base import ProviderResult
                result = ProviderResult(success=False, error=str(e))

            # 4. Record attempt
            attempt = NotificationAttempt(
                notification_id=notification.id,
                attempt_number=notification.retry_count + 1,
                status=AttemptStatusEnum.sent if result.success else AttemptStatusEnum.failed,
                provider_response={"message_id": result.provider_message_id} if result.success else {},
                error_message=result.error,
            )
            session.add(attempt)

            # 5. Handle result (Success, Retry, or Dead-letter)
            webhook_event: str | None = None
            if result.success:
                notification.status = StatusEnum.sent
                await inc_metric("notifications_sent_total", {"channel": notification.channel.value})
                logger.info("notification_sent", notification_id=notification_id_str)
                webhook_event = "notification.sent"
            else:
                logger.warning("notification_failed", notification_id=notification_id_str, error=result.error)

                if should_retry(notification.retry_count, notification.max_retries):
                    delay = calculate_backoff_delay(notification.retry_count)
                    notification.retry_count += 1
                    notification.status = StatusEnum.queued

                    # Re-enqueue with delay
                    await self.queue.enqueue_delayed(
                        notification_id=notification.id,
                        priority=notification.priority.value,
                        delay_seconds=delay,
                    )
                else:
                    # Dead-letter path: exceeded max retries
                    notification.status = StatusEnum.failed
                    await inc_metric("notifications_failed_total", {"channel": notification.channel.value})
                    logger.error(
                        "notification_dead_letter",
                        notification_id=notification_id_str,
                        retry_count=notification.retry_count,
                    )
                    webhook_event = "notification.failed"

            # Single commit for attempt + status change
            await session.commit()

            # Fire webhooks after commit (fire-and-forget; errors logged, not raised)
            if webhook_event:
                await fire_webhooks(
                    session,
                    user_id=notification.user_id,
                    event=webhook_event,
                    payload={"notification_id": notification_id_str, "channel": notification.channel.value},
                )

            structlog.contextvars.clear_contextvars()

    async def run(self) -> None:
        self.running = True
        logger.info("worker_started", concurrency=settings.WORKER_CONCURRENCY)

        # Semaphore to limit concurrent processing within a single worker process
        semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)

        async def _process_with_semaphore(notif_id: str) -> None:
            async with semaphore:
                try:
                    await self.process_notification(notif_id)
                except Exception as e:
                    logger.exception("unhandled_error_in_processing", error=str(e))

        tasks = set()

        while self.running:
            try:
                # Wait for a slot to open up before dequeuing
                await semaphore.acquire()
                
                notification_id = await self.queue.dequeue()
                if notification_id:
                    # Launch background task for processing
                    task = asyncio.create_task(_process_with_semaphore(notification_id))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                else:
                    semaphore.release()
                    await asyncio.sleep(1)  # Idle polling
                    
            except Exception as e:
                logger.exception("worker_error", error=str(e))
                try:
                    semaphore.release()
                except ValueError:
                    pass
                await asyncio.sleep(5)
                
        # Wait for remaining tasks to complete on shutdown
        if tasks:
            logger.info("waiting_for_tasks_to_finish", count=len(tasks))
            await asyncio.gather(*tasks, return_exceptions=True)


def handle_sigterm(*args: Any) -> None:
    logger.info("worker_stopping")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    worker = Worker()
    asyncio.run(worker.run())
