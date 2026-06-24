import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class TrendingSource(str, enum.Enum):
    CHANMAMA = "chanmama"
    FEIGUA = "feigua"


class SourceCandidateStatus(str, enum.Enum):
    IDENTIFIED = "identified"
    SAMPLED = "sampled"
    APPROVED = "approved"
    REJECTED = "rejected"


class OperatorDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TrendingProduct(Base):
    __tablename__ = "trending_products"

    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(256), nullable=False)
    source: Mapped[TrendingSource] = mapped_column(String(16), nullable=False)
    sales_volume_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    growth_rate_7d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    competition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_competitor_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    search_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scanned_at: Mapped[datetime] = mapped_column(nullable=False)

    source_candidates: Mapped[list["SourceCandidate"]] = relationship(
        back_populates="trending_product", cascade="all, delete-orphan"
    )
    briefs: Mapped[list["ProductBrief"]] = relationship(
        back_populates="trending_product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_trending_products_source", "source"),
        Index("ix_trending_products_category", "category"),
        Index("ix_trending_products_score", "score"),
        Index("ix_trending_products_scanned_at", "scanned_at"),
        Index("ix_trending_products_external_id", "external_id"),
    )


class SourceCandidate(Base):
    __tablename__ = "source_candidates"

    trending_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trending_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_name: Mapped[str] = mapped_column(String(256), nullable=False)
    supplier_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    wholesale_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    moq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supplier_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_location: Mapped[str] = mapped_column(String(256), nullable=False)
    sample_available: Mapped[bool] = mapped_column(default=False)
    estimated_landed_cost: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.0
    )
    estimated_margin: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.0
    )
    status: Mapped[SourceCandidateStatus] = mapped_column(
        String(16), nullable=False, default=SourceCandidateStatus.IDENTIFIED
    )

    trending_product: Mapped["TrendingProduct"] = relationship(
        back_populates="source_candidates"
    )

    __table_args__ = (
        Index("ix_source_candidates_trending_product_id", "trending_product_id"),
        Index("ix_source_candidates_status", "status"),
    )


class ProductBrief(Base):
    __tablename__ = "product_briefs"

    trending_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trending_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sourcing_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    margin_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    operator_decision: Mapped[OperatorDecision] = mapped_column(
        String(16), nullable=False, default=OperatorDecision.PENDING
    )

    trending_product: Mapped["TrendingProduct"] = relationship(
        back_populates="briefs"
    )

    __table_args__ = (
        Index("ix_product_briefs_trending_product_id", "trending_product_id"),
        Index("ix_product_briefs_operator_decision", "operator_decision"),
    )
