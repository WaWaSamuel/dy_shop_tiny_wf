"""Creative asset schemas for content generation and management."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.creative import AssetStatus, AssetType


class CreativeAssetBase(BaseModel):
    """Shared creative asset fields."""

    product_id: Optional[str] = Field(default=None)
    asset_type: AssetType = Field(..., description="Type of creative asset")
    content_url: Optional[str] = Field(default=None)
    thumbnail_url: Optional[str] = Field(default=None)
    generation_config: Optional[dict[str, Any]] = Field(default=None)
    tags: Optional[dict[str, Any]] = Field(default=None)


class CreativeAssetCreate(CreativeAssetBase):
    """Schema for creating a new creative asset."""

    parent_version_id: Optional[str] = Field(
        default=None, description="ID of the parent version for iterative generation"
    )

    @field_validator("generation_config")
    @classmethod
    def validate_generation_config(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Validate that generation config contains required keys if provided."""
        if v is not None:
            if "prompt" not in v and "template_id" not in v:
                raise ValueError("generation_config must contain 'prompt' or 'template_id'")
        return v


class PipelineRunRequest(BaseModel):
    """Request schema for triggering a creative generation pipeline."""

    product_id: str = Field(..., description="Product to generate content for")
    asset_types: list[AssetType] = Field(
        ..., min_length=1, description="Types of assets to generate"
    )
    generation_config: dict[str, Any] = Field(
        ..., description="Generation parameters (prompt, style, model)"
    )
    auto_publish: bool = Field(default=False, description="Auto-publish on completion")
    priority: int = Field(default=0, ge=0, le=10, description="Pipeline priority (0-10)")

    @field_validator("asset_types")
    @classmethod
    def validate_unique_types(cls, v: list[AssetType]) -> list[AssetType]:
        """Ensure no duplicate asset types in a single pipeline run."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate asset types are not allowed in a single pipeline run")
        return v


class GenerationResult(BaseModel):
    """Result of a single asset generation step."""

    asset_id: str = Field(description="Generated asset ID")
    asset_type: AssetType
    status: AssetStatus
    content_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    generation_time_ms: Optional[int] = Field(
        default=None, description="Generation time in milliseconds"
    )
    provider: Optional[str] = Field(default=None, description="AI provider used")
    error_message: Optional[str] = Field(default=None)
    metrics: Optional[dict[str, Any]] = None


class AssetVersionResponse(BaseModel):
    """Response showing asset version history."""

    id: str
    version: int
    asset_type: AssetType
    status: AssetStatus
    content_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    generation_config: Optional[dict[str, Any]] = None
    metrics: Optional[dict[str, Any]] = None
    tags: Optional[dict[str, Any]] = None
    parent_version_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemWordRuleCreate(BaseModel):
    """Schema for creating a system word rule."""

    word: str = Field(..., min_length=1, max_length=255, description="The word or phrase to match")
    rule_type: str = Field(
        ..., pattern="^(blocked|replacement|warning)$", description="Rule enforcement type"
    )
    replacement: Optional[str] = Field(
        default=None, max_length=255, description="Replacement text for 'replacement' rule type"
    )
    category: Optional[str] = Field(
        default=None, max_length=100, description="Rule category"
    )
    severity: str = Field(
        default="medium", pattern="^(low|medium|high)$", description="Rule severity level"
    )

    @model_validator(mode="after")
    def validate_replacement_required(self) -> "SystemWordRuleCreate":
        """Ensure replacement is provided when rule_type is 'replacement'."""
        if self.rule_type == "replacement" and not self.replacement:
            raise ValueError("Replacement text is required when rule_type is 'replacement'")
        return self
