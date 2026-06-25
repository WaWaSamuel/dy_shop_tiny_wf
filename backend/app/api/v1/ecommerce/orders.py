"""Order management endpoints."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db, get_read_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OrderItem(BaseModel):
    """Single item within an order."""

    product_id: UUID
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    variant: Optional[str] = None


class OrderCreate(BaseModel):
    """Schema for placing a new order."""

    items: List[OrderItem] = Field(..., min_length=1)
    shipping_address: Optional[str] = None
    notes: Optional[str] = None
    channel: str = Field("manual", pattern="^(manual|shopify|tiktok|amazon)$")


class OrderStatusUpdate(BaseModel):
    """Schema for updating order status."""

    status: str = Field(
        ...,
        pattern="^(pending|confirmed|processing|shipped|delivered|cancelled|refunded)$",
    )
    tracking_number: Optional[str] = None
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    """Item detail in order response."""

    product_id: UUID
    quantity: int
    unit_price: float
    variant: Optional[str] = None


class OrderResponse(BaseModel):
    """Order returned to the client."""

    id: UUID
    owner_id: str
    status: str
    channel: str
    items: List[OrderItemResponse]
    total_amount: float
    shipping_address: Optional[str]
    tracking_number: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """Paginated order list."""

    items: List[OrderResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    channel: Optional[str] = None,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """List orders with optional filtering and pagination."""
    from sqlalchemy import text

    conditions = ["o.owner_id = :owner_id"]
    params: dict = {"owner_id": user_id}

    if status_filter:
        conditions.append("o.status = :status")
        params["status"] = status_filter
    if channel:
        conditions.append("o.channel = :channel")
        params["channel"] = channel

    where_clause = " AND ".join(conditions)

    count_q = text(f"SELECT COUNT(*) FROM orders o WHERE {where_clause}")
    total = (await db.execute(count_q, params)).scalar_one()

    offset = (page - 1) * page_size
    data_q = text(
        f"SELECT o.*, COALESCE(json_agg(json_build_object("
        f"'product_id', oi.product_id, 'quantity', oi.quantity, "
        f"'unit_price', oi.unit_price, 'variant', oi.variant"
        f")) FILTER (WHERE oi.id IS NOT NULL), '[]') AS items "
        f"FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.id "
        f"WHERE {where_clause} GROUP BY o.id "
        f"ORDER BY o.created_at DESC LIMIT :limit OFFSET :offset"
    )
    params["limit"] = page_size
    params["offset"] = offset
    rows = (await db.execute(data_q, params)).mappings().all()

    items = [OrderResponse(**dict(r)) for r in rows]
    return OrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get a single order by ID."""
    from sqlalchemy import text

    query = text(
        "SELECT o.*, COALESCE(json_agg(json_build_object("
        "'product_id', oi.product_id, 'quantity', oi.quantity, "
        "'unit_price', oi.unit_price, 'variant', oi.variant"
        ")) FILTER (WHERE oi.id IS NOT NULL), '[]') AS items "
        "FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.id "
        "WHERE o.id = :id AND o.owner_id = :owner_id GROUP BY o.id"
    )
    result = await db.execute(query, {"id": str(order_id), "owner_id": user_id})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return OrderResponse(**dict(row))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Place a new order."""
    from sqlalchemy import text

    total_amount = sum(item.unit_price * item.quantity for item in payload.items)

    # Insert order
    order_q = text(
        """
        INSERT INTO orders (owner_id, status, channel, total_amount, shipping_address, notes)
        VALUES (:owner_id, 'pending', :channel, :total_amount, :shipping_address, :notes)
        RETURNING *
        """
    )
    order_row = (
        await db.execute(
            order_q,
            {
                "owner_id": user_id,
                "channel": payload.channel,
                "total_amount": total_amount,
                "shipping_address": payload.shipping_address,
                "notes": payload.notes,
            },
        )
    ).mappings().first()

    order_id = order_row["id"]

    # Insert order items
    for item in payload.items:
        item_q = text(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price, variant)
            VALUES (:order_id, :product_id, :quantity, :unit_price, :variant)
            """
        )
        await db.execute(
            item_q,
            {
                "order_id": str(order_id),
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "variant": item.variant,
            },
        )

    # Re-fetch complete order
    return await get_order(order_id, db, user_id)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Update order status and optionally tracking info."""
    from sqlalchemy import text

    set_parts = ["status = :status", "updated_at = NOW()"]
    params: dict = {"status": payload.status, "id": str(order_id), "owner_id": user_id}

    if payload.tracking_number is not None:
        set_parts.append("tracking_number = :tracking_number")
        params["tracking_number"] = payload.tracking_number
    if payload.notes is not None:
        set_parts.append("notes = :notes")
        params["notes"] = payload.notes

    query = text(
        f"UPDATE orders SET {', '.join(set_parts)} "
        f"WHERE id = :id AND owner_id = :owner_id RETURNING id"
    )
    result = await db.execute(query, params)
    if not result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return await get_order(order_id, db, user_id)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Cancel an order (only if still pending)."""
    from sqlalchemy import text

    query = text(
        "UPDATE orders SET status = 'cancelled', updated_at = NOW() "
        "WHERE id = :id AND owner_id = :owner_id AND status = 'pending' RETURNING id"
    )
    result = await db.execute(query, {"id": str(order_id), "owner_id": user_id})
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order not found or cannot be cancelled (not in pending state)",
        )
