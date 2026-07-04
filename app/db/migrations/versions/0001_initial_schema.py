"""Initial schema — all tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums ---
    channel_enum = postgresql.ENUM("email", "sms", "push", name="channelenum", create_type=False)
    channel_enum.create(op.get_bind(), checkfirst=True)

    priority_enum = postgresql.ENUM("critical", "high", "normal", "low", name="priorityenum", create_type=False)
    priority_enum.create(op.get_bind(), checkfirst=True)

    status_enum = postgresql.ENUM(
        "pending", "queued", "processing", "sent", "delivered", "failed",
        name="statusenum", create_type=False
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    attempt_status_enum = postgresql.ENUM("sent", "failed", name="attemptstatusenum", create_type=False)
    attempt_status_enum.create(op.get_bind(), checkfirst=True)

    # --- templates ---
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("channel", sa.Enum("email", "sms", "push", name="channelenum"), nullable=False),
        sa.Column("subject_template", sa.Text, nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("required_variables", postgresql.JSONB, nullable=False, server_default="[]"),
    )

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("channel", sa.Enum("email", "sms", "push", name="channelenum"), nullable=False),
        sa.Column("priority", sa.Enum("critical", "high", "normal", "low", name="priorityenum"), nullable=False),
        sa.Column("status", sa.Enum("pending", "queued", "processing", "sent", "delivered", "failed", name="statusenum"), nullable=False, server_default="pending"),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_priority", "notifications", ["priority"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_idempotency_key", "notifications", ["idempotency_key"])
    op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_status_priority_created_at", "notifications", ["status", "priority", "created_at"])

    # --- notification_attempts ---
    op.create_table(
        "notification_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("status", sa.Enum("sent", "failed", name="attemptstatusenum"), nullable=False),
        sa.Column("provider_response", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notification_attempts_notification_id", "notification_attempts", ["notification_id"])

    # --- user_preferences ---
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("channel", sa.Enum("email", "sms", "push", name="channelenum"), nullable=False),
        sa.Column("opted_in", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "channel", name="uq_user_preferences_user_channel"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    # --- idempotency_keys ---
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("key", sa.String(512), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_body", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_keys_user_key"),
    )
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"])
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])

    # --- webhooks ---
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(255), nullable=False),
        sa.Column("subscribed_events", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_webhooks_user_id", "webhooks", ["user_id"])

    # --- webhook_deliveries ---
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("idempotency_keys")
    op.drop_table("user_preferences")
    op.drop_table("notification_attempts")
    op.drop_table("notifications")
    op.drop_table("templates")

    op.execute("DROP TYPE IF EXISTS attemptstatusenum")
    op.execute("DROP TYPE IF EXISTS statusenum")
    op.execute("DROP TYPE IF EXISTS priorityenum")
    op.execute("DROP TYPE IF EXISTS channelenum")
