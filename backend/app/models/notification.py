"""Notification model for managing system alerts and messages."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class NotificationType(str, enum.Enum):
    """Types of notifications."""

    ORDER = "order"
    INVENTORY = "inventory"
    SHIPPING = "shipping"
    REVIEW = "review"
    SYSTEM = "system"
    CREATIVE = "creative"
    FLOW = "flow"
    ALERT = "alert"


class NotificationChannel(str, enum.Enum):
    """Delivery channels for notifications."""

    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PUSH = "push"


class NotificationStatus(str, enum.Enum):
    """Status of a notification."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Notification(BaseModel):
    """Notification entity for system alerts and user messages."""

    __tablename__ = "notifications"

    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"),
        default=NotificationChannel.IN_APP,
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, status={self.status})>"
