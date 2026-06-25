"""Product schemas for request validation and response serialization."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.product import ProductStatus
from app.schemas.common import PaginationMeta


class ProductBase(BaseModel):
    """Shared product fields."""

    name: str = Field(..., min_length=1, max_length=500, description="Product name")
    sku: str = Field(..., min_length=1, max_length=100, description="Stock keeping unit")
    category: Optional[str] = Field(default=None, max_length=255)
    status: ProductStatus = Field(default=ProductStatus.DRAFT)
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    platform: Optional[str] = Field(default=None, max_length=100)
    platform_product_id: Optional[str] = Field(default=None, max_length=255)
    images: Optional[dict[str, Any]] = Field(default=None)
    description: Optional[str] = Field(default=None)
    supplier_id: Optional[str] = Field(default=None)


class ProductCreate(ProductBase):
    """Schema for creating a new product."""

    @field_validator("selling_price")
    @classmethod
    def validate_selling_price(cls, v: Optional[float], info) -> Optional[float]:
        """Ensure selling price is greater than cost price if both are provided."""
        if v is not None and info.data.get("cost_price") is not None:
            if v < info.data["cost_price"]:
                raise ValueError("Selling price must be greater than or equal to cost price")
        return v


class ProductUpdate(BaseModel):
    """Schema for updating an existing product (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    sku: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[str] = Field(default=None, max_length=255)
    status: Optional[ProductStatus] = Field(default=None)
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    platform: Optional[str] = Field(default=None, max_length=100)
    platform_product_id: Optional[str] = Field(default=None, max_length=255)
    images: Optional[dict[str, Any]] = Field(default=None)
    description: Optional[str] = Field(default=None)
    supplier_id: Optional[str] = Field(default=None)


class SupplierBrief(BaseModel):
    """Brief supplier info embedded in product response."""

    id: str
    name: str
    platform: Optional[str] = None
    rating: Optional[float] = None

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    """Schema for product API responses."""

    id: str
    name: str
    sku: str
    category: Optional[str] = None
    status: ProductStatus
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    profit_margin: Optional[float] = None
    supplier_id: Optional[str] = None
    supplier: Optional[SupplierBrief] = None
    platform: Optional[str] = None
    platform_product_id: Optional[str] = None
    images: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    items: list[ProductResponse]
    pagination: PaginationMeta
