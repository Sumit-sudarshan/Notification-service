import asyncio
import random
import uuid
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import Provider, ProviderResult

logger = get_logger(__name__)

class EmailProvider(Provider):
    async def send(self, notification: Any) -> ProviderResult:
        logger.info("simulating_email_send", notification_id=str(notification.id))
        await asyncio.sleep(0.1)
        if random.random() < settings.PROVIDER_FAILURE_RATE:
            return ProviderResult(success=False, error="Simulated email provider failure")
        return ProviderResult(success=True, provider_message_id=str(uuid.uuid4()))

class SmsProvider(Provider):
    async def send(self, notification: Any) -> ProviderResult:
        logger.info("simulating_sms_send", notification_id=str(notification.id))
        await asyncio.sleep(0.1)
        if random.random() < settings.PROVIDER_FAILURE_RATE:
            return ProviderResult(success=False, error="Simulated SMS provider failure")
        return ProviderResult(success=True, provider_message_id=str(uuid.uuid4()))

class PushProvider(Provider):
    async def send(self, notification: Any) -> ProviderResult:
        logger.info("simulating_push_send", notification_id=str(notification.id))
        await asyncio.sleep(0.1)
        if random.random() < settings.PROVIDER_FAILURE_RATE:
            return ProviderResult(success=False, error="Simulated push provider failure")
        return ProviderResult(success=True, provider_message_id=str(uuid.uuid4()))

from app.providers.circuit_breaker import CircuitBreaker

_PROVIDERS: dict[str, Provider] = {}

def get_provider(channel: str) -> Provider:
    if channel not in _PROVIDERS:
        if channel == "email":
            _PROVIDERS[channel] = CircuitBreaker(EmailProvider())
        elif channel == "sms":
            _PROVIDERS[channel] = CircuitBreaker(SmsProvider())
        elif channel == "push":
            _PROVIDERS[channel] = CircuitBreaker(PushProvider())
        else:
            raise ValueError(f"Unknown channel: {channel}")
    return _PROVIDERS[channel]
