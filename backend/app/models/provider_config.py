"""Provider configuration model for managing AI/service provider settings."""

from typing import Any, Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProviderConfig(BaseModel):
    """Provider configuration entity for AI and third-party service integrations."""

    __tablename__ = "provider_configs"

    provider_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="Unique provider identifier"
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Provider category (llm, image_gen, tts, translation, shipping)",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Priority for failover ordering (higher = preferred)",
    )
    credentials: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Encrypted API keys, tokens, and auth credentials",
    )
    rate_limit_config: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Rate limiting settings (requests_per_minute, daily_quota)",
    )
    custom_params: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Provider-specific parameters (model, temperature, region)",
    )

    def __repr__(self) -> str:
        return f"<ProviderConfig(id={self.id}, provider={self.provider_id}, category={self.category})>"
