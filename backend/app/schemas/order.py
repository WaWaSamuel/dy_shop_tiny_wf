"""Order schemas for request validation and response serialization."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.order import OrderStatus


class OrderBase(BaseModel):
    """Shared order fields."""

    product_id: str = Field(..., description="ID of the ordered product")
    platform_order_id: Optional[str] = Field(default=None, max_length=255)
    buyer_info: Optional[dict[str, Any]] = Field(default=None)
    amount: float = Field(..., gt=0, description="Total order amount")
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    shipping_id: Optional[str] = Field(default=None, max_length=255)


class OrderCreate(OrderBase):
    """Schema for creating a new order."""

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Ensure amount is rounded to 2 decimal places."""
        return round(v, 2)


class OrderUpdate(BaseModel):
    """Schema for updating an existing order (all fields optional)."""

    status: Optional[OrderStatus] = Field(default=None)
    buyer_info: Optional[dict[str, Any]] = Field(default=None)
    amount: Optional[float] = Field(default=None, gt=0)
    shipping_id: Optional[str] = Field(default=None, max_length=255)
    paid_at: Optional[datetime] = Field(default=None)
    shipped_at: Optional[datetime] = Field(default=None)


class ProductBrief(BaseModel):
    """Brief product info embedded in order response."""

    id: str
    name: str
    sku: str
    platform: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Schema for order API responses."""

    id: str
    product_id: str
    product: Optional[ProductBrief] = None
    platform_order_id: Optional[str] = None
    buyer_info: Optional[dict[str, Any]] = None
    amount: float
    status: OrderStatus
    shipping_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
