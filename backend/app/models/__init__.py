"""Models package - imports all ORM models for Alembic discovery and application use."""

from app.models.base import Base, BaseModel, TimestampMixin
from app.models.creative import (
    ABTestStatus,
    AssetABTest,
    AssetStatus,
    AssetType,
    CategoryTag,
    CreativeAsset,
    SystemWordRule,
)
from app.models.flow import FlowNode, FlowNodeStatus, FlowNodeType
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from app.models.order import Order, OrderStatus
from app.models.product import Product, ProductStatus
from app.models.provider_config import ProviderConfig
from app.models.shop import Shop, ShopPlatform, ShopProduct, ShopStatus
from app.models.supplier import Supplier

__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    # Product
    "Product",
    "ProductStatus",
    # Order
    "Order",
    "OrderStatus",
    # Supplier
    "Supplier",
    # Shop
    "Shop",
    "ShopPlatform",
    "ShopProduct",
    "ShopStatus",
    # Creative
    "CreativeAsset",
    "AssetType",
    "AssetStatus",
    "AssetABTest",
    "ABTestStatus",
    "CategoryTag",
    "SystemWordRule",
    # Flow
    "FlowNode",
    "FlowNodeType",
    "FlowNodeStatus",
    # Notification
    "Notification",
    "NotificationType",
    "NotificationChannel",
    "NotificationStatus",
    # Provider
    "ProviderConfig",
]
