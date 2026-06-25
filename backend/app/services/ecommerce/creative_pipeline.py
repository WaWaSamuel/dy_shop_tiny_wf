"""Creative pipeline engine - sequential step execution with async AI calls."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of a single pipeline step execution."""

    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineStep:
    """Definition of a single step in the creative pipeline."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    step_type: str = ""  # e.g., "ai_generation", "transform", "validation"
    config: dict[str, Any] = field(default_factory=dict)
    # Callable that takes (input_data, config) and returns output
    handler: Optional[Callable] = None
    # AI provider identifier for AI steps
    ai_provider: Optional[str] = None
    ai_capability: Optional[str] = None
    # Retry configuration
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    # Condition: if set, step is skipped when condition returns False
    condition: Optional[Callable[[dict[str, Any]], bool]] = None
    # Whether this step can be skipped on failure without failing pipeline
    optional: bool = False


@dataclass
class Pipeline:
    """Creative pipeline definition."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    steps: list[PipelineStep] = field(default_factory=list)
    status: PipelineStatus = PipelineStatus.IDLE
    context: dict[str, Any] = field(default_factory=dict)
    results: list[StepResult] = field(default_factory=list)
    created_at: Optional[float] = None
    completed_at: Optional[float] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = time.time()


class CreativePipelineEngine:
    """Engine for executing creative pipelines sequentially.

    Pipelines consist of ordered steps that transform creative assets
    through AI generation, post-processing, and validation stages.
    """

    def __init__(self, ai_registry: Any = None):
        """
        Args:
            ai_registry: AIProviderRegistry instance for resolving AI providers.
        """
        self.ai_registry = ai_registry
        self._running_pipelines: dict[str, Pipeline] = {}
        self._cancel_flags: dict[str, bool] = {}

    async def execute_pipeline(
        self,
        pipeline: Pipeline,
        initial_input: Optional[dict[str, Any]] = None,
        *,
        on_step_complete: Optional[Callable[[StepResult], Any]] = None,
    ) -> Pipeline:
        """Execute a pipeline by running its steps sequentially.

        Args:
            pipeline: The pipeline definition to execute.
            initial_input: Initial data to pass to the first step.
            on_step_complete: Optional callback invoked after each step.

        Returns:
            The pipeline with results populated.
        """
        pipeline.status = PipelineStatus.RUNNING
        pipeline.context["input"] = initial_input or {}
        self._running_pipelines[pipeline.id] = pipeline
        self._cancel_flags[pipeline.id] = False

        current_data = initial_input or {}

        try:
            for step in pipeline.steps:
                # Check cancellation
                if self._cancel_flags.get(pipeline.id, False):
                    pipeline.status = PipelineStatus.CANCELLED
                    break

                # Check condition
                if step.condition and not step.condition(current_data):
                    result = StepResult(
                        step_id=step.id,
                        status=StepStatus.SKIPPED,
                        metadata={"reason": "condition_not_met"},
                    )
                    pipeline.results.append(result)
                    if on_step_complete:
                        await self._invoke_callback(on_step_complete, result)
                    continue

                # Execute step with retry
                result = await self._execute_step_with_retry(
                    step, current_data, pipeline.context
                )
                pipeline.results.append(result)

                if on_step_complete:
                    await self._invoke_callback(on_step_complete, result)

                if result.status == StepStatus.COMPLETED:
                    # Pass output to next step
                    if result.output is not None:
                        if isinstance(result.output, dict):
                            current_data = {**current_data, **result.output}
                        else:
                            current_data["_last_output"] = result.output
                    pipeline.context["last_step_output"] = result.output
                elif result.status == StepStatus.FAILED:
                    if not step.optional:
                        pipeline.status = PipelineStatus.FAILED
                        break
                    # Optional step failed - continue with warning
                    logger.warning(
                        f"Optional step '{step.name}' failed: {result.error}"
                    )

            # Set final status if not already set
            if pipeline.status == PipelineStatus.RUNNING:
                pipeline.status = PipelineStatus.COMPLETED

        except Exception as e:
            logger.error(f"Pipeline {pipeline.id} unexpected error: {e}")
            pipeline.status = PipelineStatus.FAILED
        finally:
            pipeline.completed_at = time.time()
            pipeline.context["final_output"] = current_data
            self._running_pipelines.pop(pipeline.id, None)
            self._cancel_flags.pop(pipeline.id, None)

        return pipeline

    async def _execute_step_with_retry(
        self,
        step: PipelineStep,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> StepResult:
        """Execute a step with retry logic."""
        start_time = time.monotonic()
        last_error: Optional[str] = None

        for attempt in range(step.max_retries + 1):
            try:
                if step.step_type == "ai_generation" and step.ai_provider:
                    output = await self._execute_ai_step(step, input_data)
                elif step.handler:
                    output = await self._execute_handler_step(
                        step, input_data, context
                    )
                else:
                    raise ValueError(
                        f"Step '{step.name}' has no handler or AI provider configured"
                    )

                duration_ms = (time.monotonic() - start_time) * 1000
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.COMPLETED,
                    output=output,
                    duration_ms=round(duration_ms, 2),
                    metadata={"attempts": attempt + 1},
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Step '{step.name}' attempt {attempt + 1} failed: {e}"
                )
                if attempt < step.max_retries:
                    await asyncio.sleep(
                        step.retry_delay_seconds * (attempt + 1)
                    )

        duration_ms = (time.monotonic() - start_time) * 1000
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error=last_error,
            duration_ms=round(duration_ms, 2),
            metadata={"attempts": step.max_retries + 1},
        )

    async def _execute_ai_step(
        self, step: PipelineStep, input_data: dict[str, Any]
    ) -> Any:
        """Execute an AI generation step using the AI registry."""
        if self.ai_registry is None:
            raise RuntimeError("AI registry not configured")

        provider = self.ai_registry.get_provider(
            capability=step.ai_capability,
            provider_name=step.ai_provider,
        )
        if provider is None:
            raise RuntimeError(
                f"AI provider '{step.ai_provider}' with capability "
                f"'{step.ai_capability}' not found"
            )

        # Build generation request from step config and input
        request_data = {**step.config, **input_data}
        result = await provider.generate(request_data)
        return result

    async def _execute_handler_step(
        self,
        step: PipelineStep,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """Execute a custom handler step."""
        handler = step.handler
        if handler is None:
            raise ValueError(f"No handler for step '{step.name}'")

        # Support both sync and async handlers
        if asyncio.iscoroutinefunction(handler):
            return await handler(input_data, step.config, context)
        else:
            return handler(input_data, step.config, context)

    async def _invoke_callback(
        self, callback: Callable, *args: Any
    ) -> None:
        """Invoke a callback, supporting both sync and async."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Request cancellation of a running pipeline.

        Returns:
            True if pipeline was running and cancellation was requested.
        """
        if pipeline_id in self._running_pipelines:
            self._cancel_flags[pipeline_id] = True
            return True
        return False

    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineStatus]:
        """Get current status of a pipeline."""
        pipeline = self._running_pipelines.get(pipeline_id)
        if pipeline:
            return pipeline.status
        return None


def build_creative_pipeline(
    name: str,
    product_data: dict[str, Any],
    *,
    include_video: bool = False,
) -> Pipeline:
    """Factory function to build a standard creative pipeline for product content.

    Standard flow:
    1. Generate product description (text)
    2. Enhance product images (image-to-image)
    3. Generate lifestyle images (text-to-image)
    4. Optionally generate video (image-to-video)
    5. Apply system words / compliance check
    6. Finalize and package assets

    Args:
        name: Pipeline name.
        product_data: Product information for content generation.
        include_video: Whether to include video generation step.

    Returns:
        Configured Pipeline instance.
    """
    steps = [
        PipelineStep(
            name="Generate Product Copy",
            step_type="ai_generation",
            ai_provider="openai_gpt",
            ai_capability="text_generation",
            config={
                "prompt_template": "product_description",
                "product_info": product_data,
                "max_tokens": 500,
            },
        ),
        PipelineStep(
            name="Enhance Product Images",
            step_type="ai_generation",
            ai_provider="midjourney",
            ai_capability="image_to_image",
            config={
                "style": product_data.get("style", "commercial"),
                "enhancement_level": "high",
            },
        ),
        PipelineStep(
            name="Generate Lifestyle Images",
            step_type="ai_generation",
            ai_provider="midjourney",
            ai_capability="image_to_image",
            config={
                "prompt_template": "lifestyle_scene",
                "scene_type": product_data.get("scene_type", "studio"),
            },
        ),
    ]

    if include_video:
        steps.append(
            PipelineStep(
                name="Generate Product Video",
                step_type="ai_generation",
                ai_provider="kling_video",
                ai_capability="image_to_video",
                config={
                    "duration_seconds": 5,
                    "style": "product_showcase",
                },
                optional=True,  # Video gen can fail without breaking pipeline
            )
        )

    steps.append(
        PipelineStep(
            name="Apply System Words",
            step_type="transform",
            config={"check_compliance": True},
        )
    )

    steps.append(
        PipelineStep(
            name="Package Assets",
            step_type="transform",
            config={"output_format": "asset_bundle"},
        )
    )

    return Pipeline(
        name=name,
        description=f"Creative pipeline for product: {product_data.get('title', 'Unknown')}",
        steps=steps,
        context={"product_data": product_data},
    )
