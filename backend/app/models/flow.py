"""Flow node model for tracking product workflow pipeline stages."""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class FlowNodeType(str, enum.Enum):
    """Types of flow pipeline nodes."""

    PRODUCT_SELECTION = "product_selection"
    SUPPLIER_MATCH = "supplier_match"
    CONTENT_GENERATION = "content_generation"
    LISTING_CREATION = "listing_creation"
    QUALITY_CHECK = "quality_check"
    PUBLISHING = "publishing"
    MONITORING = "monitoring"
    OPTIMIZATION = "optimization"


class FlowNodeStatus(str, enum.Enum):
    """Execution status of a flow node."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class FlowNode(BaseModel):
    """Flow node entity representing a step in the product pipeline workflow."""

    __tablename__ = "flow_nodes"

    product_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[FlowNodeType] = mapped_column(
        Enum(FlowNodeType, name="flow_node_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[FlowNodeStatus] = mapped_column(
        Enum(FlowNodeStatus, name="flow_node_status"),
        default=FlowNodeStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    node_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Node configuration and context data",
    )
    logs: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Execution logs and output data",
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="flow_nodes", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<FlowNode(id={self.id}, type={self.node_type}, status={self.status})>"
