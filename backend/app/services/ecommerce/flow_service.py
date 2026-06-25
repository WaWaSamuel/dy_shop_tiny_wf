"""Flow service - get/update flow nodes for a product."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession


class FlowNodeStatus:
    """Status constants for flow nodes."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


# Default product workflow definition
DEFAULT_FLOW_TEMPLATE: list[dict[str, Any]] = [
    {
        "node_key": "sourcing",
        "label": "Product Sourcing",
        "order": 1,
        "required": True,
    },
    {
        "node_key": "listing_draft",
        "label": "Listing Draft",
        "order": 2,
        "required": True,
    },
    {
        "node_key": "creative_generation",
        "label": "Creative Generation",
        "order": 3,
        "required": True,
    },
    {
        "node_key": "system_words",
        "label": "System Words Check",
        "order": 4,
        "required": True,
    },
    {
        "node_key": "quality_review",
        "label": "Quality Review",
        "order": 5,
        "required": True,
    },
    {
        "node_key": "platform_publish",
        "label": "Platform Publish",
        "order": 6,
        "required": True,
    },
    {
        "node_key": "live_monitoring",
        "label": "Live Monitoring",
        "order": 7,
        "required": False,
    },
]


class FlowService:
    """Service for managing product workflow (flow) nodes.

    Each product goes through a defined workflow with discrete steps.
    This service tracks progress and allows updating node states.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_flow(self, product_id: UUID) -> dict[str, Any]:
        """Get the complete flow for a product.

        If no flow exists, initializes from the default template.

        Args:
            product_id: UUID of the product.

        Returns:
            Flow data with nodes and overall progress.
        """
        from app.models.product_flow import ProductFlow, FlowNode  # type: ignore[import]

        # Check for existing flow
        stmt = select(ProductFlow).where(ProductFlow.product_id == product_id)
        result = await self.db.execute(stmt)
        flow = result.scalar_one_or_none()

        if flow is None:
            # Initialize default flow
            flow = await self._initialize_flow(product_id)

        # Get all nodes
        nodes_stmt = (
            select(FlowNode)
            .where(FlowNode.flow_id == flow.id)
            .order_by(FlowNode.order.asc())
        )
        nodes_result = await self.db.execute(nodes_stmt)
        nodes = nodes_result.scalars().all()

        return self._serialize_flow(flow, nodes)

    async def update_node(
        self,
        product_id: UUID,
        node_key: str,
        *,
        status: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
        operator: str = "system",
    ) -> dict[str, Any]:
        """Update a specific flow node for a product.

        Args:
            product_id: UUID of the product.
            node_key: Identifier of the node to update.
            status: New status value.
            data: Additional node data/metadata.
            operator: Who performed the update.

        Returns:
            Updated flow data.

        Raises:
            ValueError: If node not found or invalid status transition.
        """
        from app.models.product_flow import ProductFlow, FlowNode  # type: ignore[import]

        # Get flow
        flow_stmt = select(ProductFlow).where(ProductFlow.product_id == product_id)
        flow_result = await self.db.execute(flow_stmt)
        flow = flow_result.scalar_one_or_none()

        if flow is None:
            flow = await self._initialize_flow(product_id)

        # Get the target node
        node_stmt = select(FlowNode).where(
            and_(FlowNode.flow_id == flow.id, FlowNode.node_key == node_key)
        )
        node_result = await self.db.execute(node_stmt)
        node = node_result.scalar_one_or_none()

        if node is None:
            raise ValueError(
                f"Node '{node_key}' not found in flow for product {product_id}"
            )

        # Update status
        if status:
            self._validate_status_transition(node.status, status)
            node.status = status
            node.updated_at = datetime.utcnow()

            # Record status change
            if not node.metadata:
                node.metadata = {}
            history = node.metadata.get("history", [])
            history.append({
                "status": status,
                "operator": operator,
                "timestamp": datetime.utcnow().isoformat(),
            })
            node.metadata["history"] = history

            # Auto-advance: if completed, unblock next node
            if status == FlowNodeStatus.COMPLETED:
                await self._try_unblock_next(flow.id, node.order)

        # Update data
        if data:
            if not node.metadata:
                node.metadata = {}
            node.metadata.update(data)
            node.updated_at = datetime.utcnow()

        # Update flow progress
        await self._update_flow_progress(flow)

        await self.db.flush()

        # Return full flow
        return await self.get_flow(product_id)

    async def reset_node(
        self, product_id: UUID, node_key: str
    ) -> dict[str, Any]:
        """Reset a node back to pending status.

        Args:
            product_id: Product UUID.
            node_key: Node to reset.

        Returns:
            Updated flow data.
        """
        return await self.update_node(
            product_id, node_key, status=FlowNodeStatus.PENDING, operator="reset"
        )

    async def _initialize_flow(self, product_id: UUID) -> Any:
        """Create a new flow from the default template."""
        from app.models.product_flow import ProductFlow, FlowNode  # type: ignore[import]

        flow = ProductFlow(
            product_id=product_id,
            status="active",
            progress=0.0,
            metadata={},
        )
        self.db.add(flow)
        await self.db.flush()

        # Create nodes from template
        for i, template in enumerate(DEFAULT_FLOW_TEMPLATE):
            node = FlowNode(
                flow_id=flow.id,
                node_key=template["node_key"],
                label=template["label"],
                order=template["order"],
                required=template["required"],
                status=(
                    FlowNodeStatus.PENDING
                    if i == 0
                    else FlowNodeStatus.BLOCKED
                ),
                metadata={},
            )
            self.db.add(node)

        # First node should be pending (unblocked)
        await self.db.flush()
        return flow

    async def _try_unblock_next(self, flow_id: UUID, current_order: int) -> None:
        """Unblock the next node in sequence after current completes."""
        from app.models.product_flow import FlowNode  # type: ignore[import]

        next_stmt = (
            select(FlowNode)
            .where(
                and_(
                    FlowNode.flow_id == flow_id,
                    FlowNode.order == current_order + 1,
                )
            )
        )
        result = await self.db.execute(next_stmt)
        next_node = result.scalar_one_or_none()

        if next_node and next_node.status == FlowNodeStatus.BLOCKED:
            next_node.status = FlowNodeStatus.PENDING
            next_node.updated_at = datetime.utcnow()

    async def _update_flow_progress(self, flow: Any) -> None:
        """Recalculate flow progress percentage."""
        from app.models.product_flow import FlowNode  # type: ignore[import]

        nodes_stmt = select(FlowNode).where(
            and_(FlowNode.flow_id == flow.id, FlowNode.required == True)
        )
        result = await self.db.execute(nodes_stmt)
        required_nodes = result.scalars().all()

        if not required_nodes:
            flow.progress = 100.0
            return

        completed = sum(
            1
            for n in required_nodes
            if n.status == FlowNodeStatus.COMPLETED
        )
        flow.progress = round((completed / len(required_nodes)) * 100, 1)
        flow.updated_at = datetime.utcnow()

        # Check if all required nodes are completed
        if completed == len(required_nodes):
            flow.status = "completed"

    @staticmethod
    def _validate_status_transition(current: str, target: str) -> None:
        """Validate that a status transition is allowed."""
        valid_transitions: dict[str, list[str]] = {
            FlowNodeStatus.BLOCKED: [FlowNodeStatus.PENDING],
            FlowNodeStatus.PENDING: [
                FlowNodeStatus.IN_PROGRESS,
                FlowNodeStatus.SKIPPED,
            ],
            FlowNodeStatus.IN_PROGRESS: [
                FlowNodeStatus.COMPLETED,
                FlowNodeStatus.FAILED,
                FlowNodeStatus.PENDING,  # Allow retry
            ],
            FlowNodeStatus.COMPLETED: [FlowNodeStatus.PENDING],  # Allow redo
            FlowNodeStatus.FAILED: [
                FlowNodeStatus.PENDING,
                FlowNodeStatus.IN_PROGRESS,
            ],
            FlowNodeStatus.SKIPPED: [FlowNodeStatus.PENDING],
        }

        allowed = valid_transitions.get(current, [])
        if target not in allowed:
            raise ValueError(
                f"Cannot transition from '{current}' to '{target}'. "
                f"Allowed: {allowed}"
            )

    @staticmethod
    def _serialize_flow(flow: Any, nodes: list[Any]) -> dict[str, Any]:
        """Serialize flow with nodes."""
        return {
            "id": str(flow.id),
            "product_id": str(flow.product_id),
            "status": flow.status,
            "progress": flow.progress,
            "nodes": [
                {
                    "node_key": node.node_key,
                    "label": node.label,
                    "order": node.order,
                    "required": node.required,
                    "status": node.status,
                    "metadata": node.metadata,
                    "updated_at": (
                        node.updated_at.isoformat()
                        if node.updated_at
                        else None
                    ),
                }
                for node in nodes
            ],
            "created_at": flow.created_at.isoformat() if flow.created_at else None,
            "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
        }
