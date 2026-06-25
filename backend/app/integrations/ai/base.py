"""AI provider base classes and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AICapabilityType(str, Enum):
    """Types of AI capabilities supported."""

    TEXT_GENERATION = "text_generation"
    IMAGE_TO_IMAGE = "image_to_image"
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_VIDEO = "image_to_video"
    TEXT_TO_VIDEO = "text_to_video"
    BACKGROUND_REMOVAL = "background_removal"
    UPSCALE = "upscale"
    STYLE_TRANSFER = "style_transfer"
    OBJECT_DETECTION = "object_detection"
    OCR = "ocr"


@dataclass
class AIProviderMeta:
    """Metadata describing an AI provider's capabilities and limits."""

    provider_name: str
    display_name: str
    capabilities: list[AICapabilityType]
    max_concurrent_requests: int = 5
    rate_limit_rpm: int = 60  # Requests per minute
    supports_batch: bool = False
    supported_formats: list[str] = field(default_factory=lambda: ["png", "jpg"])
    max_resolution: Optional[tuple[int, int]] = None
    pricing_unit: str = "per_request"
    estimated_cost_per_unit: float = 0.0
    description: str = ""
    version: str = "1.0.0"


@dataclass
class GenerationRequest:
    """Request for AI generation."""

    # Common fields
    request_id: str = ""
    capability: AICapabilityType = AICapabilityType.TEXT_GENERATION
    prompt: str = ""
    negative_prompt: str = ""

    # Text generation
    max_tokens: int = 1024
    temperature: float = 0.7
    system_prompt: str = ""

    # Image generation / transformation
    input_image_url: Optional[str] = None
    input_images: list[str] = field(default_factory=list)
    width: int = 1024
    height: int = 1024
    num_outputs: int = 1
    style: str = ""
    strength: float = 0.75  # For img2img: how much to transform

    # Video generation
    input_video_url: Optional[str] = None
    duration_seconds: float = 5.0
    fps: int = 24

    # Advanced
    seed: Optional[int] = None
    model_version: Optional[str] = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    # Callback
    webhook_url: Optional[str] = None


@dataclass
class GenerationResult:
    """Result from AI generation."""

    request_id: str = ""
    success: bool = False
    capability: AICapabilityType = AICapabilityType.TEXT_GENERATION

    # Text output
    text: Optional[str] = None

    # Image/video outputs
    output_urls: list[str] = field(default_factory=list)
    thumbnail_urls: list[str] = field(default_factory=list)

    # Metadata
    model_used: str = ""
    processing_time_ms: float = 0.0
    tokens_used: Optional[int] = None
    cost: float = 0.0
    seed_used: Optional[int] = None

    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Raw response for debugging
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseAIProvider(ABC):
    """Abstract base class for AI generation providers.

    All AI providers (text, image, video) implement this interface.
    """

    @property
    @abstractmethod
    def meta(self) -> AIProviderMeta:
        """Get provider metadata."""
        ...

    @property
    def provider_name(self) -> str:
        """Shortcut to provider name."""
        return self.meta.provider_name

    @property
    def capabilities(self) -> list[AICapabilityType]:
        """Shortcut to capabilities list."""
        return self.meta.capabilities

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Execute an AI generation request.

        Args:
            request: The generation request with all parameters.

        Returns:
            GenerationResult with outputs or error information.
        """
        ...

    async def check_health(self) -> bool:
        """Check if the provider is healthy and reachable.

        Default implementation returns True. Override for actual health checks.
        """
        return True

    async def estimate_cost(self, request: GenerationRequest) -> float:
        """Estimate the cost of a generation request.

        Default implementation uses metadata pricing.
        """
        return self.meta.estimated_cost_per_unit * request.num_outputs

    async def cancel_request(self, request_id: str) -> bool:
        """Attempt to cancel a pending request.

        Not all providers support cancellation. Default returns False.
        """
        return False

    def supports_capability(self, capability: AICapabilityType) -> bool:
        """Check if this provider supports a given capability."""
        return capability in self.capabilities
