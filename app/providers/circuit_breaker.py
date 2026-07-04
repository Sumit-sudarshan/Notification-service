import time
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.providers.base import Provider, ProviderResult

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreaker(Provider):
    """
    A simple Circuit Breaker wrapper around a Provider.
    """

    def __init__(
        self,
        provider: Provider,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def send(self, notification: Any) -> ProviderResult:
        now = time.time()

        # Check state transitions
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open", provider=self.provider.__class__.__name__)
            else:
                logger.warning("circuit_breaker_open_rejected", provider=self.provider.__class__.__name__)
                return ProviderResult(
                    success=False, error="Circuit breaker is OPEN. Request rejected."
                )

        # We are CLOSED or HALF_OPEN. Try the request.
        try:
            result = await self.provider.send(notification)
        except Exception as e:
            result = ProviderResult(success=False, error=str(e))

        # Handle result
        if result.success:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("circuit_breaker_closed", provider=self.provider.__class__.__name__)
            else:
                # Reset failure count on success when CLOSED
                self.failure_count = 0
        else:
            self.failure_count += 1
            self.last_failure_time = now
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.error(
                        "circuit_breaker_tripped",
                        provider=self.provider.__class__.__name__,
                        failure_count=self.failure_count,
                    )
                self.state = CircuitState.OPEN

        return result
