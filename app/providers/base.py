import abc
from pydantic import BaseModel
from typing import Any

class ProviderResult(BaseModel):
    success: bool
    provider_message_id: str | None = None
    error: str | None = None

class Provider(abc.ABC):
    @abc.abstractmethod
    async def send(self, notification: Any) -> ProviderResult:
        """Send the notification via the provider channel."""
        pass
