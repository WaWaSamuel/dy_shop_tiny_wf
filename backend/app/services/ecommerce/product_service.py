"""Product service - CRUD operations with filtering and pagination."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.pagination import PaginatedResult, paginate_query


class ProductFilter:
    """Filter parameters for product listing."""

    def __init__(
        self,
        *,
        category_id: Optional[UUID] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        tags: Optional[list[str]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        self.category_id = category_id
        self.status = status
        self.keyword = keyword
        self.min_price = min_price
        self.max_price = max_price
        self.tags = tags
        self.created_after = created_after
        self.created_before = created_before


class ProductService:
    """Service for product CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_product(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new product.

        Args:
            data: Product creation payload including title, description,
                  category_id, price, images, tags, etc.

        Returns:
            The created product as a dictionary.
        """
        from app.models.product import Product  # type: ignore[import]

        product = Product(
            title=data["title"],
            description=data.get("description", ""),
            category_id=data.get("category_id"),
            price=data["price"],
            cost_price=data.get("cost_price"),
            images=data.get("images", []),
            tags=data.get("tags", []),
            status="draft",
            metadata=data.get("metadata", {}),
        )
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        return self._serialize(product)

    async def get_product(self, product_id: UUID) -> Optional[dict[str, Any]]:
        """Retrieve a single product by ID."""
        from app.models.product import Product  # type: ignore[import]

        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            return None
        return self._serialize(product)

    async def update_product(
        self, product_id: UUID, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Update an existing product.

        Args:
            product_id: The UUID of the product to update.
            data: Partial update payload.

        Returns:
            Updated product or None if not found.
        """
        from app.models.product import Product  # type: ignore[import]

        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            return None

        updatable_fields = [
            "title", "description", "category_id", "price",
            "cost_price", "images", "tags", "status", "metadata",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(product, field, data[field])

        product.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(product)
        return self._serialize(product)

    async def delete_product(self, product_id: UUID) -> bool:
        """Soft-delete a product by setting status to 'deleted'.

        Returns:
            True if product was found and deleted, False otherwise.
        """
        from app.models.product import Product  # type: ignore[import]

        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            return False

        product.status = "deleted"
        product.updated_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def list_products(
        self,
        filters: Optional[ProductFilter] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "created_at",
        order_dir: str = "desc",
    ) -> PaginatedResult:
        """List products with filters and pagination.

        Args:
            filters: Optional filter parameters.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            order_by: Column name to order by.
            order_dir: 'asc' or 'desc'.

        Returns:
            PaginatedResult with items and pagination metadata.
        """
        from app.models.product import Product  # type: ignore[import]

        stmt = select(Product).where(Product.status != "deleted")

        if filters:
            conditions = []
            if filters.category_id:
                conditions.append(Product.category_id == filters.category_id)
            if filters.status:
                conditions.append(Product.status == filters.status)
            if filters.keyword:
                like_pattern = f"%{filters.keyword}%"
                conditions.append(
                    Product.title.ilike(like_pattern)
                    | Product.description.ilike(like_pattern)
                )
            if filters.min_price is not None:
                conditions.append(Product.price >= filters.min_price)
            if filters.max_price is not None:
                conditions.append(Product.price <= filters.max_price)
            if filters.created_after:
                conditions.append(Product.created_at >= filters.created_after)
            if filters.created_before:
                conditions.append(Product.created_at <= filters.created_before)
            if conditions:
                stmt = stmt.where(and_(*conditions))

        # Ordering
        order_column = getattr(Product, order_by, Product.created_at)
        if order_dir == "asc":
            stmt = stmt.order_by(order_column.asc())
        else:
            stmt = stmt.order_by(order_column.desc())

        return await paginate_query(self.db, stmt, page, page_size, self._serialize)

    async def bulk_update_status(
        self, product_ids: list[UUID], status: str
    ) -> int:
        """Bulk update product status.

        Returns:
            Number of products updated.
        """
        from app.models.product import Product  # type: ignore[import]

        stmt = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .where(Product.status != "deleted")
        )
        result = await self.db.execute(stmt)
        products = result.scalars().all()

        count = 0
        for product in products:
            product.status = status
            product.updated_at = datetime.utcnow()
            count += 1

        await self.db.flush()
        return count

    @staticmethod
    def _serialize(product: Any) -> dict[str, Any]:
        """Convert product model to dictionary."""
        return {
            "id": str(product.id),
            "title": product.title,
            "description": product.description,
            "category_id": str(product.category_id) if product.category_id else None,
            "price": float(product.price) if product.price else None,
            "cost_price": float(product.cost_price) if product.cost_price else None,
            "images": product.images,
            "tags": product.tags,
            "status": product.status,
            "metadata": product.metadata,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        }
