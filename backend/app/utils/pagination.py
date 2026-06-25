"""Pagination helper utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


@dataclass
class PaginatedResult:
    """Standardized pagination response."""

    items: list[Any] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False

    @property
    def metadata(self) -> dict[str, Any]:
        """Return pagination metadata as dict."""
        return {
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


async def paginate_query(
    db: AsyncSession,
    query: Select,
    page: int = 1,
    page_size: int = 20,
    serializer: Optional[Callable[[Any], Any]] = None,
) -> PaginatedResult:
    """Execute a SQLAlchemy query with pagination.

    Args:
        db: Async database session.
        query: SQLAlchemy select statement.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        serializer: Optional function to serialize each result item.

    Returns:
        PaginatedResult with items and pagination metadata.
    """
    # Validate inputs
    page = max(1, page)
    page_size = max(1, min(page_size, 100))  # Cap at 100

    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    # Apply offset and limit
    offset = (page - 1) * page_size
    paginated_query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    # Serialize items if serializer provided
    if serializer:
        serialized_items = [serializer(item) for item in items]
    else:
        serialized_items = list(items)

    return PaginatedResult(
        items=serialized_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def paginate_list(
    items: list[Any],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResult:
    """Paginate an in-memory list.

    Useful for paginating results that are already loaded in memory
    (e.g., from external APIs or cached data).

    Args:
        items: Full list of items.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        PaginatedResult with the appropriate slice.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    total = len(items)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return PaginatedResult(
        items=page_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


class CursorPaginator:
    """Cursor-based pagination for large datasets.

    More efficient than offset-based pagination for large tables
    as it doesn't need to count total rows.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        page_size: int = 20,
        cursor_field: str = "id",
    ):
        self.db = db
        self.page_size = max(1, min(page_size, 100))
        self.cursor_field = cursor_field

    async def paginate(
        self,
        query: Select,
        model: Any,
        *,
        cursor: Optional[str] = None,
        direction: str = "next",
        serializer: Optional[Callable[[Any], Any]] = None,
    ) -> dict[str, Any]:
        """Execute cursor-based pagination.

        Args:
            query: Base SQLAlchemy select.
            model: SQLAlchemy model class.
            cursor: Cursor value (ID of last seen item).
            direction: 'next' or 'prev'.
            serializer: Optional item serializer.

        Returns:
            Dict with items, next_cursor, prev_cursor, has_more.
        """
        cursor_col = getattr(model, self.cursor_field)

        if cursor:
            if direction == "next":
                query = query.where(cursor_col > cursor)
            else:
                query = query.where(cursor_col < cursor)

        # Fetch one extra to determine has_more
        query = query.limit(self.page_size + 1)

        if direction == "next":
            query = query.order_by(cursor_col.asc())
        else:
            query = query.order_by(cursor_col.desc())

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        has_more = len(items) > self.page_size
        if has_more:
            items = items[: self.page_size]

        # Reverse if going backwards
        if direction == "prev":
            items.reverse()

        # Serialize
        if serializer:
            serialized = [serializer(item) for item in items]
        else:
            serialized = items

        # Build cursors
        next_cursor = None
        prev_cursor = None

        if items:
            last_item = items[-1]
            first_item = items[0]
            next_cursor = str(getattr(last_item, self.cursor_field)) if has_more else None
            prev_cursor = str(getattr(first_item, self.cursor_field)) if cursor else None

        return {
            "items": serialized,
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
            "has_more": has_more,
            "page_size": self.page_size,
        }
