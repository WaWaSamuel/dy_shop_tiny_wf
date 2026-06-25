"""Product model for managing product listings across platforms."""

import enum
from typing import Any, Optional

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ProductStatus(str, enum.Enum):
    """Product lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class Product(BaseModel):
    """Product entity representing a sellable item across platforms."""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status"),
        default=ProductStatus.DRAFT,
        nullable=False,
        index=True,
    )
    cost_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Cost price from supplier"
    )
    selling_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Selling price to customer"
    )
    profit_margin: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Calculated profit margin percentage"
    )
    supplier_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Primary platform (e.g., shopify, tiktok)"
    )
    platform_product_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Product ID on the external platform"
    )
    images: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="List of image URLs and metadata"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    supplier: Mapped[Optional["Supplier"]] = relationship(  # noqa: F821
        "Supplier", back_populates="products", lazy="selectin"
    )
    orders: Mapped[list["Order"]] = relationship(  # noqa: F821
        "Order", back_populates="product", lazy="selectin"
    )
    creative_assets: Mapped[list["CreativeAsset"]] = relationship(  # noqa: F821
        "CreativeAsset", back_populates="product", lazy="selectin"
    )
    flow_nodes: Mapped[list["FlowNode"]] = relationship(  # noqa: F821
        "FlowNode", back_populates="product", lazy="selectin"
    )
    shop_products: Mapped[list["ShopProduct"]] = relationship(  # noqa: F821
        "ShopProduct", back_populates="product", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name})>"
