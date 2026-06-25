"""Product CRUD endpoints."""

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


class ProductBase(BaseModel):
    """Shared product fields."""

    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=64)
    price: float = Field(..., ge=0)
    cost: Optional[float] = Field(None, ge=0)
    currency: str = Field("USD", max_length=3)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str = Field("draft", pattern="^(draft|active|archived)$")


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product (all optional)."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=64)
    price: Optional[float] = Field(None, ge=0)
    cost: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class ProductResponse(ProductBase):
    """Schema returned to the client."""

    id: UUID
    owner_id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Paginated product list."""

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """List products for the authenticated user with filtering and pagination."""
    # Build query dynamically
    from sqlalchemy import func, select, text

    conditions = ["owner_id = :owner_id"]
    params: dict = {"owner_id": user_id}

    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter
    if category:
        conditions.append("category = :category")
        params["category"] = category
    if search:
        conditions.append("(title ILIKE :search OR description ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(conditions)

    count_query = text(f"SELECT COUNT(*) FROM products WHERE {where_clause}")
    result = await db.execute(count_query, params)
    total = result.scalar_one()

    offset = (page - 1) * page_size
    data_query = text(
        f"SELECT * FROM products WHERE {where_clause} "
        f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    )
    params["limit"] = page_size
    params["offset"] = offset
    result = await db.execute(data_query, params)
    rows = result.mappings().all()

    items = [ProductResponse(**dict(r)) for r in rows]
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get a single product by ID."""
    from sqlalchemy import text

    query = text("SELECT * FROM products WHERE id = :id AND owner_id = :owner_id")
    result = await db.execute(query, {"id": str(product_id), "owner_id": user_id})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductResponse(**dict(row))


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a new product."""
    from sqlalchemy import text

    query = text(
        """
        INSERT INTO products (title, description, sku, price, cost, currency, category, tags, status, owner_id)
        VALUES (:title, :description, :sku, :price, :cost, :currency, :category, :tags, :status, :owner_id)
        RETURNING *
        """
    )
    params = {
        **payload.model_dump(),
        "tags": payload.tags,
        "owner_id": user_id,
    }
    result = await db.execute(query, params)
    row = result.mappings().first()
    return ProductResponse(**dict(row))


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Partially update a product."""
    from sqlalchemy import text

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    query = text(
        f"UPDATE products SET {set_clauses}, updated_at = NOW() "
        f"WHERE id = :id AND owner_id = :owner_id RETURNING *"
    )
    params = {**updates, "id": str(product_id), "owner_id": user_id}
    result = await db.execute(query, params)
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductResponse(**dict(row))


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a product (soft-delete by setting status to archived)."""
    from sqlalchemy import text

    query = text(
        "UPDATE products SET status = 'archived', updated_at = NOW() "
        "WHERE id = :id AND owner_id = :owner_id RETURNING id"
    )
    result = await db.execute(query, {"id": str(product_id), "owner_id": user_id})
    if not result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
