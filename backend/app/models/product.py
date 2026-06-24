import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ONLINE = "online"
    OFFLINE = "offline"


class ProductSource(str, enum.Enum):
    MANUAL = "manual"
    IMPORT_1688 = "1688_import"
    DISCOVERY = "discovery"


class Product(Base):
    __tablename__ = "products"

    douyin_product_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    category_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ProductStatus] = mapped_column(
        String(16), nullable=False, default=ProductStatus.DRAFT
    )
    images: Mapped[list[Any]] = mapped_column(JSON, default=list)
    sku_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price_range: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[ProductSource] = mapped_column(
        String(16), nullable=False, default=ProductSource.MANUAL
    )
    listing_submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    listing_approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    skus: Mapped[list["ProductSKU"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_products_status", "status"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_source", "source"),
        Index("ix_products_douyin_product_id", "douyin_product_id"),
    )


class ProductSKU(Base):
    __tablename__ = "product_skus"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    sku_name: Mapped[str] = mapped_column(String(256), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    market_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sku_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="skus")

    __table_args__ = (
        Index("ix_product_skus_product_id", "product_id"),
    )


class CategoryMapping(Base):
    __tablename__ = "category_mappings"

    category_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    category_name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    required_attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    image_requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_category_mappings_parent_id", "parent_id"),
    )
