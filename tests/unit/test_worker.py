"""
Worker unit tests — mock all external dependencies (DB session, Redis, provider)
and verify the worker's internal state machine is correct.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.notification import ChannelEnum, Notification, PriorityEnum, StatusEnum
from app.workers.notification_worker import Worker


def _make_notification(retry_count: int = 0, max_retries: int = 3) -> Notification:
    n = Notification()
    n.id = uuid.uuid4()
    n.user_id = "user-test"
    n.channel = ChannelEnum.email
    n.priority = PriorityEnum.normal
    n.status = StatusEnum.queued
    n.retry_count = retry_count
    n.max_retries = max_retries
    n.correlation_id = None
    n.payload = {"body": "Hello"}
    return n


@pytest.mark.asyncio
async def test_worker_success_sets_status_sent():
    """Provider succeeds → status becomes 'sent'."""
    notification = _make_notification()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=notification)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    from app.providers.base import ProviderResult
    mock_provider = AsyncMock()
    mock_provider.send = AsyncMock(return_value=ProviderResult(success=True, provider_message_id="msg-1"))

    with (
        patch("app.workers.notification_worker.AsyncSessionLocal", return_value=mock_session_cm),
        patch("app.workers.notification_worker.get_provider", return_value=mock_provider),
        patch("app.workers.notification_worker.inc_metric", AsyncMock()),
        patch("app.workers.notification_worker.fire_webhooks", AsyncMock()),
    ):
        worker = Worker()
        worker.redis = AsyncMock()
        worker.queue = AsyncMock()
        await worker.process_notification(str(notification.id))

    assert notification.status == StatusEnum.sent


@pytest.mark.asyncio
async def test_worker_failure_retries_then_dead_letters():
    """Provider always fails → after max retries, status becomes 'failed'."""
    notification = _make_notification(retry_count=3, max_retries=3)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=notification)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    from app.providers.base import ProviderResult
    mock_provider = AsyncMock()
    mock_provider.send = AsyncMock(return_value=ProviderResult(success=False, error="Provider down"))

    with (
        patch("app.workers.notification_worker.AsyncSessionLocal", return_value=mock_session_cm),
        patch("app.workers.notification_worker.get_provider", return_value=mock_provider),
        patch("app.workers.notification_worker.inc_metric", AsyncMock()),
        patch("app.workers.notification_worker.fire_webhooks", AsyncMock()),
    ):
        worker = Worker()
        worker.redis = AsyncMock()
        worker.queue = AsyncMock()
        await worker.process_notification(str(notification.id))

    # retry_count already at max → should be dead-lettered
    assert notification.status == StatusEnum.failed
