"""Product flow/node endpoints for workflow automation."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db, get_read_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NodeType(str, Enum):
    """Types of flow nodes."""

    SOURCE = "source"
    TRANSFORM = "transform"
    DECISION = "decision"
    ACTION = "action"
    OUTPUT = "output"


class NodeStatus(str, Enum):
    """Execution status for a node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FlowCreate(BaseModel):
    """Create a new product flow."""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    product_id: Optional[UUID] = None
    trigger: Optional[Dict[str, Any]] = None  # e.g. {"type": "manual"} or {"type": "schedule", "cron": "..."}


class FlowUpdate(BaseModel):
    """Update flow metadata."""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    trigger: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class NodeCreate(BaseModel):
    """Add a node to a flow."""

    flow_id: UUID
    node_type: NodeType
    label: str = Field(..., max_length=100)
    config: Dict[str, Any] = Field(default_factory=dict)
    position_x: float = 0
    position_y: float = 0
    depends_on: List[UUID] = Field(default_factory=list, description="IDs of upstream nodes")


class NodeUpdate(BaseModel):
    """Update a node."""

    label: Optional[str] = Field(None, max_length=100)
    config: Optional[Dict[str, Any]] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    depends_on: Optional[List[UUID]] = None


class EdgeCreate(BaseModel):
    """Create an edge between two nodes."""

    flow_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    condition: Optional[Dict[str, Any]] = None  # Optional conditional logic


class FlowResponse(BaseModel):
    """Flow returned to client."""

    id: UUID
    owner_id: str
    name: str
    description: Optional[str]
    product_id: Optional[UUID]
    trigger: Optional[Dict[str, Any]]
    is_active: bool
    nodes_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class NodeResponse(BaseModel):
    """Node returned to client."""

    id: UUID
    flow_id: UUID
    node_type: str
    label: str
    config: Dict[str, Any]
    position_x: float
    position_y: float
    depends_on: List[UUID]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class EdgeResponse(BaseModel):
    """Edge returned to client."""

    id: UUID
    flow_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    condition: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class FlowExecutionResponse(BaseModel):
    """Result of executing a flow."""

    flow_id: UUID
    execution_id: UUID
    status: str
    nodes_executed: int
    nodes_failed: int
    results: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Endpoints - Flows
# ---------------------------------------------------------------------------


@router.get("/flows", response_model=List[FlowResponse])
async def list_flows(
    product_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """List all flows for the current user."""
    from sqlalchemy import text

    conditions = ["f.owner_id = :owner_id"]
    params: dict = {"owner_id": user_id}

    if product_id:
        conditions.append("f.product_id = :product_id")
        params["product_id"] = str(product_id)
    if is_active is not None:
        conditions.append("f.is_active = :is_active")
        params["is_active"] = is_active

    where_clause = " AND ".join(conditions)
    query = text(
        f"SELECT f.*, (SELECT COUNT(*) FROM flow_nodes fn WHERE fn.flow_id = f.id) AS nodes_count "
        f"FROM flows f WHERE {where_clause} ORDER BY f.updated_at DESC"
    )
    rows = (await db.execute(query, params)).mappings().all()
    return [FlowResponse(**dict(r)) for r in rows]


@router.post("/flows", response_model=FlowResponse, status_code=status.HTTP_201_CREATED)
async def create_flow(
    payload: FlowCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a new product flow."""
    from sqlalchemy import text

    query = text(
        """
        INSERT INTO flows (owner_id, name, description, product_id, trigger_config, is_active)
        VALUES (:owner_id, :name, :description, :product_id, :trigger_config, true)
        RETURNING *, 0 AS nodes_count
        """
    )
    row = (
        await db.execute(
            query,
            {
                "owner_id": user_id,
                "name": payload.name,
                "description": payload.description,
                "product_id": str(payload.product_id) if payload.product_id else None,
                "trigger_config": payload.trigger or {},
            },
        )
    ).mappings().first()
    result = dict(row)
    result["trigger"] = result.pop("trigger_config", None)
    return FlowResponse(**result)


@router.patch("/flows/{flow_id}", response_model=FlowResponse)
async def update_flow(
    flow_id: UUID,
    payload: FlowUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Update flow metadata."""
    from sqlalchemy import text

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    # Rename trigger -> trigger_config for DB
    if "trigger" in updates:
        updates["trigger_config"] = updates.pop("trigger")

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    query = text(
        f"UPDATE flows SET {set_clauses}, updated_at = NOW() "
        f"WHERE id = :id AND owner_id = :owner_id "
        f"RETURNING *, (SELECT COUNT(*) FROM flow_nodes fn WHERE fn.flow_id = flows.id) AS nodes_count"
    )
    params = {**updates, "id": str(flow_id), "owner_id": user_id}
    row = (await db.execute(query, params)).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    result = dict(row)
    result["trigger"] = result.pop("trigger_config", None)
    return FlowResponse(**result)


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a flow and its nodes/edges."""
    from sqlalchemy import text

    result = await db.execute(
        text("DELETE FROM flows WHERE id = :id AND owner_id = :owner_id RETURNING id"),
        {"id": str(flow_id), "owner_id": user_id},
    )
    if not result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")


# ---------------------------------------------------------------------------
# Endpoints - Nodes
# ---------------------------------------------------------------------------


@router.get("/flows/{flow_id}/nodes", response_model=List[NodeResponse])
async def list_nodes(
    flow_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """List all nodes in a flow."""
    from sqlalchemy import text

    # Verify ownership
    check = await db.execute(
        text("SELECT id FROM flows WHERE id = :id AND owner_id = :owner_id"),
        {"id": str(flow_id), "owner_id": user_id},
    )
    if not check.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    query = text(
        "SELECT * FROM flow_nodes WHERE flow_id = :flow_id ORDER BY position_y, position_x"
    )
    rows = (await db.execute(query, {"flow_id": str(flow_id)})).mappings().all()
    return [NodeResponse(**dict(r)) for r in rows]


@router.post("/nodes", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    payload: NodeCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Add a node to a flow."""
    from sqlalchemy import text

    # Verify ownership
    check = await db.execute(
        text("SELECT id FROM flows WHERE id = :id AND owner_id = :owner_id"),
        {"id": str(payload.flow_id), "owner_id": user_id},
    )
    if not check.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    query = text(
        """
        INSERT INTO flow_nodes (flow_id, node_type, label, config, position_x, position_y, depends_on, status)
        VALUES (:flow_id, :node_type, :label, :config, :position_x, :position_y, :depends_on, 'pending')
        RETURNING *
        """
    )
    row = (
        await db.execute(
            query,
            {
                "flow_id": str(payload.flow_id),
                "node_type": payload.node_type.value,
                "label": payload.label,
                "config": payload.config,
                "position_x": payload.position_x,
                "position_y": payload.position_y,
                "depends_on": [str(d) for d in payload.depends_on],
            },
        )
    ).mappings().first()
    return NodeResponse(**dict(row))


@router.patch("/nodes/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: UUID,
    payload: NodeUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Update a node."""
    from sqlalchemy import text

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    if "depends_on" in updates and updates["depends_on"] is not None:
        updates["depends_on"] = [str(d) for d in updates["depends_on"]]

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    query = text(
        f"UPDATE flow_nodes SET {set_clauses} "
        f"WHERE id = :id AND flow_id IN (SELECT id FROM flows WHERE owner_id = :owner_id) "
        f"RETURNING *"
    )
    params = {**updates, "id": str(node_id), "owner_id": user_id}
    row = (await db.execute(query, params)).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return NodeResponse(**dict(row))


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a node from a flow."""
    from sqlalchemy import text

    result = await db.execute(
        text(
            "DELETE FROM flow_nodes WHERE id = :id "
            "AND flow_id IN (SELECT id FROM flows WHERE owner_id = :owner_id) RETURNING id"
        ),
        {"id": str(node_id), "owner_id": user_id},
    )
    if not result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")


# ---------------------------------------------------------------------------
# Endpoints - Edges
# ---------------------------------------------------------------------------


@router.post("/edges", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge(
    payload: EdgeCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a directed edge between two nodes."""
    from sqlalchemy import text

    # Verify flow ownership
    check = await db.execute(
        text("SELECT id FROM flows WHERE id = :id AND owner_id = :owner_id"),
        {"id": str(payload.flow_id), "owner_id": user_id},
    )
    if not check.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    query = text(
        """
        INSERT INTO flow_edges (flow_id, source_node_id, target_node_id, condition)
        VALUES (:flow_id, :source_node_id, :target_node_id, :condition)
        RETURNING *
        """
    )
    row = (
        await db.execute(
            query,
            {
                "flow_id": str(payload.flow_id),
                "source_node_id": str(payload.source_node_id),
                "target_node_id": str(payload.target_node_id),
                "condition": payload.condition,
            },
        )
    ).mappings().first()
    return EdgeResponse(**dict(row))


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(
    edge_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete an edge."""
    from sqlalchemy import text

    result = await db.execute(
        text(
            "DELETE FROM flow_edges WHERE id = :id "
            "AND flow_id IN (SELECT id FROM flows WHERE owner_id = :owner_id) RETURNING id"
        ),
        {"id": str(edge_id), "owner_id": user_id},
    )
    if not result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")


# ---------------------------------------------------------------------------
# Endpoints - Execution
# ---------------------------------------------------------------------------


@router.post("/flows/{flow_id}/execute", response_model=FlowExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_flow(
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Trigger execution of a flow. Processing is handled asynchronously."""
    from sqlalchemy import text

    # Verify flow ownership and active state
    check = await db.execute(
        text("SELECT id, is_active FROM flows WHERE id = :id AND owner_id = :owner_id"),
        {"id": str(flow_id), "owner_id": user_id},
    )
    row = check.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    if not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flow is inactive")

    # Create execution record
    exec_q = text(
        """
        INSERT INTO flow_executions (flow_id, owner_id, status, nodes_executed, nodes_failed, results)
        VALUES (:flow_id, :owner_id, 'running', 0, 0, '[]')
        RETURNING *
        """
    )
    exec_row = (
        await db.execute(exec_q, {"flow_id": str(flow_id), "owner_id": user_id})
    ).mappings().first()

    return FlowExecutionResponse(
        flow_id=flow_id,
        execution_id=exec_row["id"],
        status="running",
        nodes_executed=0,
        nodes_failed=0,
        results=[],
    )
