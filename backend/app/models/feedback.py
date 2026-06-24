import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FeedbackSource(str, enum.Enum):
    REVIEW = "review"
    IM = "im"
    AFTER_SALE = "after_sale"
    QA = "qa"
    VIDEO_COMMENT = "video_comment"


class FeedbackType(str, enum.Enum):
    PRODUCT_QUALITY = "product_quality"
    LOGISTICS = "logistics"
    PRICING = "pricing"
    CUSTOMER_SERVICE = "customer_service"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class FeedbackStatus(str, enum.Enum):
    PENDING = "pending"
    AUTO_REPLIED = "auto_replied"
    HUMAN_REVIEW = "human_review"
    RESOLVED = "resolved"


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    source: Mapped[FeedbackSource] = mapped_column(String(32), nullable=False)
    type: Mapped[FeedbackType] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[Sentiment] = mapped_column(String(16), nullable=False)
    urgency: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    status: Mapped[FeedbackStatus] = mapped_column(
        String(16), nullable=False, default=FeedbackStatus.PENDING
    )
    auto_reply_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    human_reply_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_feedback_events_product_id", "product_id"),
        Index("ix_feedback_events_status", "status"),
        Index("ix_feedback_events_source", "source"),
        Index("ix_feedback_events_timestamp", "timestamp"),
        Index("ix_feedback_events_urgency", "urgency"),
    )


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"

    category: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_knowledge_base_entries_category", "category"),
        Index("ix_knowledge_base_entries_product_id", "product_id"),
    )


class ResponseTemplate(Base):
    __tablename__ = "response_templates"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_response_templates_category", "category"),
    )
