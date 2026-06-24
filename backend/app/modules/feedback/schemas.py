"""Data models and enums for the feedback module."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FeedbackSource(str, enum.Enum):
    """Channel from which feedback was received."""

    REVIEW = "review"
    IM = "im"
    AFTER_SALE = "after_sale"


class FeedbackType(str, enum.Enum):
    """Classification category for feedback content."""

    PRODUCT_QUALITY = "product_quality"
    LOGISTICS = "logistics"
    PRICING = "pricing"
    CUSTOMER_SERVICE = "customer_service"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(str, enum.Enum):
    """Sentiment analysis result."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class FeedbackStatus(str, enum.Enum):
    """Processing status of a feedback event."""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    DRAFT_READY = "draft_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    REPLIED = "replied"
    ESCALATED = "escalated"
    IGNORED = "ignored"


class FeedbackEvent(BaseModel):
    """Normalized feedback event from any channel."""

    id: str = ""
    source: FeedbackSource
    external_id: str = ""
    order_id: str = ""
    product_id: str = ""
    customer_id: str = ""
    customer_name: str = ""
    content: str = ""
    star_rating: int | None = None
    images: list[str] = Field(default_factory=list)
    refund_amount: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    received_at: datetime = Field(default_factory=datetime.utcnow)

    # Classification results (populated after processing)
    feedback_type: FeedbackType | None = None
    sentiment: Sentiment | None = None
    urgency_score: int = 0
    status: FeedbackStatus = FeedbackStatus.PENDING

    # Response
    auto_reply: str = ""
    final_reply: str = ""
    replied_at: datetime | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    """Result of AI classification pipeline."""

    feedback_type: FeedbackType
    sentiment: Sentiment
    urgency_score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class KBEntry(BaseModel):
    """Knowledge base entry for FAQ matching."""

    id: str = ""
    question: str
    answer: str
    category: str = ""
    product_id: str = ""
    similarity_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
