"""Creative asset models for AI-generated content management."""

import enum
from typing import Any, Optional

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AssetType(str, enum.Enum):
    """Types of creative assets."""

    IMAGE = "image"
    VIDEO = "video"
    COPY = "copy"
    THUMBNAIL = "thumbnail"
    BANNER = "banner"
    AD_CREATIVE = "ad_creative"
    PRODUCT_PHOTO = "product_photo"
    LIFESTYLE_PHOTO = "lifestyle_photo"


class AssetStatus(str, enum.Enum):
    """Status of a creative asset."""

    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CreativeAsset(BaseModel):
    """Creative asset entity for AI-generated product content."""

    __tablename__ = "creative_assets"

    product_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="Version number for iterative generation"
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status"),
        default=AssetStatus.PENDING,
        nullable=False,
        index=True,
    )
    content_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="URL to the generated content file"
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="URL to thumbnail preview"
    )
    generation_config: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="AI generation parameters (prompt, model, settings)",
    )
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Performance metrics (CTR, engagement, conversion)",
    )
    tags: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Tags and labels for categorization",
    )
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("creative_assets.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to previous version for version chain",
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="creative_assets", lazy="selectin"
    )
    parent_version: Mapped[Optional["CreativeAsset"]] = relationship(
        "CreativeAsset",
        remote_side="CreativeAsset.id",
        foreign_keys=[parent_version_id],
        lazy="selectin",
    )
    ab_tests: Mapped[list["AssetABTest"]] = relationship(
        "AssetABTest",
        back_populates="asset",
        foreign_keys="AssetABTest.asset_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<CreativeAsset(id={self.id}, type={self.asset_type}, version={self.version})>"


class ABTestStatus(str, enum.Enum):
    """Status of an A/B test."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssetABTest(BaseModel):
    """A/B test entity for comparing creative asset performance."""

    __tablename__ = "asset_ab_tests"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("creative_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_asset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("creative_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ABTestStatus] = mapped_column(
        Enum(ABTestStatus, name="ab_test_status"),
        default=ABTestStatus.DRAFT,
        nullable=False,
    )
    traffic_split: Mapped[Optional[float]] = mapped_column(
        Float, default=0.5, comment="Traffic split ratio for variant (0.0-1.0)"
    )
    results: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Test results and statistical metrics"
    )
    winner_asset_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True, comment="ID of the winning asset"
    )

    # Relationships
    asset: Mapped["CreativeAsset"] = relationship(
        "CreativeAsset",
        back_populates="ab_tests",
        foreign_keys=[asset_id],
        lazy="selectin",
    )
    variant_asset: Mapped["CreativeAsset"] = relationship(
        "CreativeAsset",
        foreign_keys=[variant_asset_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AssetABTest(id={self.id}, name={self.name}, status={self.status})>"


class CategoryTag(BaseModel):
    """Category tags for organizing creative assets."""

    __tablename__ = "category_tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("category_tags.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True, comment="Hex color code for UI display"
    )

    # Self-referential relationship
    parent: Mapped[Optional["CategoryTag"]] = relationship(
        "CategoryTag", remote_side="CategoryTag.id", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<CategoryTag(id={self.id}, name={self.name})>"


class SystemWordRule(BaseModel):
    """System word rules for content generation compliance."""

    __tablename__ = "system_word_rules"

    word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Rule type: blocked, replacement, warning",
    )
    replacement: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Replacement word if rule_type is replacement"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Category: legal, brand, sensitivity"
    )
    severity: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default="medium", comment="Severity: low, medium, high"
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<SystemWordRule(id={self.id}, word={self.word}, type={self.rule_type})>"
