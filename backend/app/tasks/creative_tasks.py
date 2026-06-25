"""Async tasks for AI generation pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine in a sync context (Celery task)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.creative_tasks.run_creative_pipeline",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def run_creative_pipeline(
    self: Any,
    product_id: str,
    pipeline_config: dict[str, Any],
) -> dict[str, Any]:
    """Execute a full creative pipeline for a product.

    This task orchestrates the generation of all creative assets
    (images, videos, copy) for a product.

    Args:
        product_id: UUID of the product.
        pipeline_config: Configuration for the pipeline steps.

    Returns:
        Pipeline execution result.
    """
    logger.info(f"Starting creative pipeline for product {product_id}")

    async def _execute() -> dict[str, Any]:
        from app.services.ecommerce.creative_pipeline import (
            CreativePipelineEngine,
            build_creative_pipeline,
        )
        from app.integrations.ai.registry import get_ai_registry

        ai_registry = get_ai_registry()
        engine = CreativePipelineEngine(ai_registry=ai_registry)

        # Build pipeline from config
        pipeline = build_creative_pipeline(
            name=f"Creative pipeline for {product_id}",
            product_data=pipeline_config.get("product_data", {}),
            include_video=pipeline_config.get("include_video", False),
        )

        # Execute pipeline
        result = await engine.execute_pipeline(
            pipeline,
            initial_input=pipeline_config.get("initial_input", {}),
        )

        return {
            "pipeline_id": result.id,
            "status": result.status.value,
            "steps_completed": len([
                r for r in result.results if r.status.value == "completed"
            ]),
            "steps_failed": len([
                r for r in result.results if r.status.value == "failed"
            ]),
            "total_steps": len(result.steps),
            "context": result.context.get("final_output", {}),
        }

    try:
        result = _run_async(_execute())
        logger.info(
            f"Creative pipeline completed for product {product_id}: "
            f"status={result['status']}"
        )
        return result
    except Exception as exc:
        logger.error(
            f"Creative pipeline failed for product {product_id}: {exc}"
        )
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(
    name="app.tasks.creative_tasks.generate_product_images",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
)
def generate_product_images(
    self: Any,
    product_id: str,
    image_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate enhanced product images using AI.

    Args:
        product_id: UUID of the product.
        image_config: Image generation configuration including style,
                      source images, and enhancement parameters.

    Returns:
        Generated image URLs and metadata.
    """
    logger.info(f"Generating product images for {product_id}")

    async def _execute() -> dict[str, Any]:
        from app.integrations.ai.registry import get_ai_registry
        from app.integrations.ai.base import (
            AICapabilityType,
            GenerationRequest,
        )

        registry = get_ai_registry()
        provider = registry.get_provider(capability=AICapabilityType.IMAGE_TO_IMAGE)

        if provider is None:
            raise RuntimeError("No image-to-image provider available")

        request = GenerationRequest(
            capability=AICapabilityType.IMAGE_TO_IMAGE,
            prompt=image_config.get("prompt", ""),
            input_image_url=image_config.get("source_image_url"),
            width=image_config.get("width", 1024),
            height=image_config.get("height", 1024),
            num_outputs=image_config.get("num_outputs", 4),
            style=image_config.get("style", "commercial"),
            strength=image_config.get("strength", 0.75),
        )

        result = await provider.generate(request)

        return {
            "success": result.success,
            "output_urls": result.output_urls,
            "thumbnail_urls": result.thumbnail_urls,
            "model_used": result.model_used,
            "cost": result.cost,
            "error": result.error_message,
        }

    try:
        result = _run_async(_execute())
        logger.info(
            f"Image generation completed for {product_id}: "
            f"{len(result.get('output_urls', []))} images"
        )
        return result
    except Exception as exc:
        logger.error(f"Image generation failed for {product_id}: {exc}")
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


@celery_app.task(
    name="app.tasks.creative_tasks.generate_product_video",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=900,
)
def generate_product_video(
    self: Any,
    product_id: str,
    video_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate a product showcase video from images.

    Args:
        product_id: UUID of the product.
        video_config: Video generation configuration.

    Returns:
        Generated video URL and metadata.
    """
    logger.info(f"Generating product video for {product_id}")

    async def _execute() -> dict[str, Any]:
        from app.integrations.ai.registry import get_ai_registry
        from app.integrations.ai.base import (
            AICapabilityType,
            GenerationRequest,
        )

        registry = get_ai_registry()
        provider = registry.get_provider(capability=AICapabilityType.IMAGE_TO_VIDEO)

        if provider is None:
            raise RuntimeError("No image-to-video provider available")

        request = GenerationRequest(
            capability=AICapabilityType.IMAGE_TO_VIDEO,
            prompt=video_config.get("prompt", ""),
            input_image_url=video_config.get("source_image_url"),
            duration_seconds=video_config.get("duration", 5.0),
            fps=video_config.get("fps", 24),
            width=video_config.get("width", 1920),
            height=video_config.get("height", 1080),
        )

        result = await provider.generate(request)

        return {
            "success": result.success,
            "video_url": result.output_urls[0] if result.output_urls else None,
            "thumbnail_url": (
                result.thumbnail_urls[0] if result.thumbnail_urls else None
            ),
            "model_used": result.model_used,
            "cost": result.cost,
            "error": result.error_message,
        }

    try:
        result = _run_async(_execute())
        logger.info(f"Video generation completed for {product_id}")
        return result
    except Exception as exc:
        logger.error(f"Video generation failed for {product_id}: {exc}")
        raise self.retry(exc=exc, countdown=120 * (self.request.retries + 1))


@celery_app.task(
    name="app.tasks.creative_tasks.generate_product_copy",
    bind=True,
    max_retries=3,
    soft_time_limit=60,
)
def generate_product_copy(
    self: Any,
    product_id: str,
    copy_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate product copywriting using AI.

    Args:
        product_id: UUID of the product.
        copy_config: Copy generation configuration (type, tone, keywords).

    Returns:
        Generated text content.
    """
    logger.info(f"Generating product copy for {product_id}")

    async def _execute() -> dict[str, Any]:
        from app.integrations.ai.registry import get_ai_registry
        from app.integrations.ai.base import (
            AICapabilityType,
            GenerationRequest,
        )

        registry = get_ai_registry()
        provider = registry.get_provider(capability=AICapabilityType.TEXT_GENERATION)

        if provider is None:
            raise RuntimeError("No text generation provider available")

        request = GenerationRequest(
            capability=AICapabilityType.TEXT_GENERATION,
            prompt=copy_config.get("prompt", ""),
            system_prompt=copy_config.get("system_prompt", ""),
            max_tokens=copy_config.get("max_tokens", 1024),
            temperature=copy_config.get("temperature", 0.7),
        )

        result = await provider.generate(request)

        return {
            "success": result.success,
            "text": result.text,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "cost": result.cost,
            "error": result.error_message,
        }

    try:
        result = _run_async(_execute())
        logger.info(f"Copy generation completed for {product_id}")
        return result
    except Exception as exc:
        logger.error(f"Copy generation failed for {product_id}: {exc}")
        raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1))


@celery_app.task(
    name="app.tasks.creative_tasks.apply_system_words",
    soft_time_limit=30,
)
def apply_system_words(
    product_id: str,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Apply system word rules to generated text.

    Args:
        product_id: UUID of the product.
        text: Text content to process.
        context: Context with category, tags, platform info.

    Returns:
        Processed text with compliance info.
    """
    logger.info(f"Applying system words for product {product_id}")

    from app.services.ecommerce.system_words import get_system_word_engine

    engine = get_system_word_engine()
    result = engine.apply_rules(
        text,
        category=context.get("category"),
        tags=context.get("tags"),
        platform=context.get("platform"),
    )

    return {
        "original_text": result.original_text,
        "modified_text": result.modified_text,
        "rules_applied": result.rules_applied,
        "is_compliant": result.is_compliant,
        "violations": result.violations,
        "words_added": result.words_added,
        "words_replaced": result.words_replaced,
    }
