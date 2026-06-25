"""Shop model for managing multi-platform shop connections."""

import enum
from typing import Any, Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ShopPlatform(str, enum.Enum):
    """Supported e-commerce platforms."""

    SHOPIFY = "shopify"
    TIKTOK_SHOP = "tiktok_shop"
    AMAZON = "amazon"
    EBAY = "ebay"
    ETSY = "etsy"
    WOOCOMMERCE = "woocommerce"
    ALIEXPRESS = "aliexpress"
    OTHER = "other"


class ShopStatus(str, enum.Enum):
    """Shop connection status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_AUTH = "pending_auth"
    AUTH_EXPIRED = "auth_expired"


class Shop(BaseModel):
    """Shop entity representing a connected e-commerce storefront."""

    __tablename__ = "shops"

    shop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[ShopPlatform] = mapped_column(
        Enum(ShopPlatform, name="shop_platform"),
        nullable=False,
        index=True,
    )
    platform_shop_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        comment="Shop ID on the external platform",
    )
    credentials: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Encrypted OAuth tokens and API keys",
    )
    status: Mapped[ShopStatus] = mapped_column(
        Enum(ShopStatus, name="shop_status"),
        default=ShopStatus.PENDING_AUTH,
        nullable=False,
        index=True,
    )
    sync_config: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Sync schedule, field mappings, and automation rules",
    )

    # Relationships
    shop_products: Mapped[list["ShopProduct"]] = relationship(
        "ShopProduct", back_populates="shop", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shop(id={self.id}, shop_name={self.shop_name}, platform={self.platform})>"


class ShopProduct(BaseModel):
    """Mapping between shops and products for multi-platform product sync."""

    __tablename__ = "shop_products"

    shop_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_listing_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Listing ID on the shop platform"
    )
    sync_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default="pending"
    )
    platform_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Direct URL to the listing"
    )
    platform_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Platform-specific listing metadata"
    )

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="shop_products", lazy="selectin")
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="shop_products", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ShopProduct(shop_id={self.shop_id}, product_id={self.product_id})>"
