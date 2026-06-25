"""Common schemas for API responses, pagination, and shared types."""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Field name to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort direction")

    @property
    def offset(self) -> int:
        """Calculate SQL offset from page and page_size."""
        return (self.page - 1) * self.page_size


class PaginationMeta(BaseModel):
    """Pagination metadata in list responses."""

    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")

    @classmethod
    def from_params(cls, total: int, params: PaginationParams) -> "PaginationMeta":
        """Create pagination metadata from total count and query params."""
        total_pages = (total + params.page_size - 1) // params.page_size
        return cls(
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
        )


class SourceInfo(BaseModel):
    """Information about a data source or integration origin."""

    platform: str = Field(description="Source platform identifier")
    source_id: Optional[str] = Field(default=None, description="ID on the source platform")
    source_url: Optional[str] = Field(default=None, description="URL to the source item")
    synced_at: Optional[str] = Field(default=None, description="Last sync timestamp (ISO 8601)")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Extra source metadata")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(default=True, description="Whether the request was successful")
    message: str = Field(default="ok", description="Human-readable status message")
    data: Optional[T] = Field(default=None, description="Response payload")
    errors: Optional[list[dict[str, Any]]] = Field(
        default=None, description="List of error details if success is False"
    )

    @classmethod
    def ok(cls, data: Any = None, message: str = "ok") -> "APIResponse":
        """Create a successful response."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(
        cls, message: str = "An error occurred", errors: Optional[list[dict[str, Any]]] = None
    ) -> "APIResponse":
        """Create an error response."""
        return cls(success=False, message=message, data=None, errors=errors)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response wrapper."""

    success: bool = Field(default=True)
    message: str = Field(default="ok")
    data: list[T] = Field(default_factory=list)
    pagination: PaginationMeta
