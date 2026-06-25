"""Flow schemas for pipeline visualization and monitoring."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.flow import FlowNodeStatus, FlowNodeType


class FlowNodeResponse(BaseModel):
    """Response schema for a single flow node."""

    id: str
    product_id: Optional[str] = None
    node_type: FlowNodeType
    status: FlowNodeStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = Field(
        default=None, description="Calculated duration in seconds"
    )
    metadata: Optional[dict[str, Any]] = None
    logs: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_duration(cls, obj: Any) -> "FlowNodeResponse":
        """Create response with calculated duration from ORM object."""
        duration = None
        if obj.started_at and obj.completed_at:
            duration = (obj.completed_at - obj.started_at).total_seconds()
        return cls(
            id=obj.id,
            product_id=obj.product_id,
            node_type=obj.node_type,
            status=obj.status,
            started_at=obj.started_at,
            completed_at=obj.completed_at,
            duration_seconds=duration,
            metadata=obj.node_metadata,
            logs=obj.logs,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class FlowNodeSummary(BaseModel):
    """Compact node summary for overview display."""

    node_type: FlowNodeType
    status: FlowNodeStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FlowOverviewResponse(BaseModel):
    """Response schema for a complete product flow overview."""

    product_id: str
    product_name: Optional[str] = None
    nodes: list[FlowNodeSummary] = Field(default_factory=list)
    total_nodes: int = Field(default=0)
    completed_nodes: int = Field(default=0)
    failed_nodes: int = Field(default=0)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    current_stage: Optional[FlowNodeType] = Field(
        default=None, description="Currently active or next pending stage"
    )
    estimated_completion: Optional[datetime] = Field(
        default=None, description="Estimated completion time"
    )
