import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.notification import ChannelEnum, PriorityEnum, StatusEnum
from app.models.notification_attempt import AttemptStatusEnum


class NotificationAttemptSchema(BaseModel):
    id: uuid.UUID
    attempt_number: int
    status: AttemptStatusEnum
    provider_response: dict[str, Any]
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    user_id: str = Field(..., max_length=255)
    channel: ChannelEnum
    priority: PriorityEnum = PriorityEnum.normal
    template_id: uuid.UUID | None = None
    template_variables: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    subject: str | None = None
    scheduled_at: datetime | None = None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    channel: ChannelEnum
    priority: PriorityEnum
    status: StatusEnum
    template_id: uuid.UUID | None
    payload: dict[str, Any]
    idempotency_key: str | None
    retry_count: int
    max_retries: int
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationDetailResponse(NotificationResponse):
    attempts: list[NotificationAttemptSchema]
