import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ChannelEnum(str, enum.Enum):
    email = "email"
    sms = "sms"
    push = "push"


class PriorityEnum(str, enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class StatusEnum(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    processing = "processing"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[ChannelEnum] = mapped_column(Enum(ChannelEnum), nullable=False)
    priority: Mapped[PriorityEnum] = mapped_column(Enum(PriorityEnum), nullable=False, index=True)
    status: Mapped[StatusEnum] = mapped_column(Enum(StatusEnum), nullable=False, default=StatusEnum.pending, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    attempts: Mapped[list["NotificationAttempt"]] = relationship("NotificationAttempt", back_populates="notification", cascade="all, delete-orphan")
    template: Mapped["Template | None"] = relationship("Template", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index("ix_notifications_status_priority_created_at", "status", "priority", "created_at"),
    )
