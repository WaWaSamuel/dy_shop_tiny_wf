import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ListingStatus(str, enum.Enum):
    """Lifecycle of a sourced listing (selected product -> 抖店 listing)."""

    MATCHING = "matching"          # searching 1688 for a same-source supply
    MATCHED = "matched"            # supplier found, pricing computed
    NO_SOURCE = "no_source"        # no acceptable 1688 match found
    LISTING = "listing"            # submitting to 抖店
    LISTED = "listed"              # live on 抖店 (or under review)
    LISTING_FAILED = "listing_failed"


class OrderStatus(str, enum.Enum):
    """Lifecycle of a 抖店 order through 1688 fulfillment."""

    RECEIVED = "received"          # order ingested from 抖店 (webhook/poll)
    SOURCING = "sourcing"          # placing the matching 1688 order
    SOURCED = "sourced"            # 1688 order placed (awaiting payment/ship)
    SHIPPED = "shipped"            # supplier shipped; tracking active
    DELIVERED = "delivered"        # logistics signed
    FULFILL_FAILED = "fulfill_failed"
    CANCELLED = "cancelled"


class SupplierOrderStatus(str, enum.Enum):
    """Lifecycle of the upstream 1688 purchase order."""

    CREATED = "created"            # created on 1688, awaiting payment
    PAID = "paid"
    SHIPPED = "shipped"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourcedListing(Base):
    """Links a selected discovery candidate to its 1688 supply and 抖店 listing.

    One sourced listing captures the full picture for flow 1: the matched
    1688 货源, the computed sell price (target margin >= configured floor),
    and the resulting 抖店 商品.
    """

    __tablename__ = "sourced_listings"

    # Source: discovery candidate this listing was sourced from (optional).
    source_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Resulting 抖店 product (set once listed).
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    # 1688 matched supply.
    alibaba_offer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    supplier_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    delivery_location: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    match_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    # Pricing snapshot.
    wholesale_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    landed_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    sell_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    target_margin: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    achieved_margin: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    # Resolved 1688 SKU map and ad assets used for the listing.
    sku_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    asset_urls: Mapped[list[Any]] = mapped_column(JSON, default=list)

    douyin_product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[ListingStatus] = mapped_column(
        String(20), nullable=False, default=ListingStatus.MATCHING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="listing")

    __table_args__ = (
        Index("ix_sourced_listings_status", "status"),
        Index("ix_sourced_listings_alibaba_offer_id", "alibaba_offer_id"),
        Index("ix_sourced_listings_douyin_product_id", "douyin_product_id"),
        Index("ix_sourced_listings_product_id", "product_id"),
    )


class Order(Base):
    """A 抖店 buyer order that must be fulfilled via a 1688 purchase."""

    __tablename__ = "orders"

    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sourced_listings.id", ondelete="SET NULL"),
        nullable=True,
    )

    douyin_order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    douyin_product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sku_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    buyer_paid_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)

    # Encrypted/opaque shipping payload as received from 抖店.
    receiver_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    status: Mapped[OrderStatus] = mapped_column(
        String(20), nullable=False, default=OrderStatus.RECEIVED
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    listing: Mapped[Optional["SourcedListing"]] = relationship(back_populates="orders")
    supplier_order: Mapped[Optional["SupplierOrder"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ix_orders_status", "status"),
        Index("ix_orders_douyin_order_id", "douyin_order_id"),
        Index("ix_orders_listing_id", "listing_id"),
    )


class SupplierOrder(Base):
    """The upstream 1688 purchase order placed to fulfill a 抖店 order."""

    __tablename__ = "supplier_orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    alibaba_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    alibaba_offer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)

    status: Mapped[SupplierOrderStatus] = mapped_column(
        String(20), nullable=False, default=SupplierOrderStatus.CREATED
    )

    # Logistics summary mirrored from the latest LogisticsTrack.
    tracking_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    logistics_company: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="supplier_order")
    tracks: Mapped[list["LogisticsTrack"]] = relationship(
        back_populates="supplier_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_supplier_orders_status", "status"),
        Index("ix_supplier_orders_alibaba_order_id", "alibaba_order_id"),
        Index("ix_supplier_orders_order_id", "order_id"),
    )


class LogisticsTrack(Base):
    """A point-in-time logistics trace snapshot for a supplier order."""

    __tablename__ = "logistics_tracks"

    supplier_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    tracking_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    logistics_company: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # Ordered list of trace events: [{"time": ..., "desc": ...}].
    trace_detail: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # Whether this trace has been pushed back to 抖店 as a shipment.
    synced_to_douyin: Mapped[bool] = mapped_column(default=False)

    supplier_order: Mapped["SupplierOrder"] = relationship(back_populates="tracks")

    __table_args__ = (
        Index("ix_logistics_tracks_supplier_order_id", "supplier_order_id"),
        Index("ix_logistics_tracks_tracking_no", "tracking_no"),
    )
