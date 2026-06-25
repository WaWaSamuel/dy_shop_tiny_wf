"""Order model for tracking customer orders across platforms."""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderStatus(str, enum.Enum):
    """Order lifecycle status."""

    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class Order(BaseModel):
    """Order entity representing a customer purchase."""

    __tablename__ = "orders"

    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_order_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Order ID on the external platform",
    )
    buyer_info: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Buyer details (name, address, contact) - PII encrypted at rest",
    )
    amount: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Total order amount"
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )
    shipping_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Shipping/tracking identifier"
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="orders", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, platform_order_id={self.platform_order_id}, status={self.status})>"
