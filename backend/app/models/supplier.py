"""Supplier model for managing supplier information."""

from typing import Any, Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Supplier(BaseModel):
    """Supplier entity representing a product supplier/vendor."""

    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Supplier platform (e.g., 1688, AliExpress)"
    )
    rating: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Supplier rating (0-5)"
    )
    delivery_speed: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Average delivery speed in days"
    )
    return_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Return rate as decimal (0.0-1.0)"
    )
    credentials: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Encrypted credentials for supplier API access",
    )

    # Relationships
    products: Mapped[list["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="supplier", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name={self.name}, platform={self.platform})>"
