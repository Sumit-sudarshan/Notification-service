import uuid

from sqlalchemy import Enum, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.notification import ChannelEnum


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    channel: Mapped[ChannelEnum] = mapped_column(Enum(ChannelEnum), nullable=False)
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    required_variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="template")  # noqa: F821
