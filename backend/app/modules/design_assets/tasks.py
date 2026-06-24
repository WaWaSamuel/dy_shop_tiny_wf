"""Celery tasks for asynchronous design asset generation.

Provides async task wrappers for the design asset pipeline, enabling
background processing of image generation without blocking the API.
"""

import asyncio
import logging
from typing import Optional

from celery import shared_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="design_assets.process_design_task",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_design_task_async(self, task_id: str):
    """Process a design task asynchronously through the full pipeline.

    This is the primary Celery task that executes the complete design generation
    pipeline: background removal, AI generation, compositing, and upload.

    Args:
        task_id: ID of the DesignTask to process.
    """
    from .service import DesignAssetService

    logger.info("Celery task started: process_design_task (task_id=%s)", task_id)

    service = DesignAssetService()
    try:
        result = _run_async(service.process_task(task_id))
        logger.info(
            "Celery task completed: task_id=%s, status=%s, outputs=%d",
            task_id,
            result.status.value,
            len(result.output_images),
        )
        return {
            "task_id": task_id,
            "status": result.status.value,
            "output_images": result.output_images,
        }
    except Exception as exc:
        logger.error("Celery task failed: task_id=%s, error=%s", task_id, str(exc))
        # Retry on transient failures
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        _run_async(service.close())


@shared_task(
    bind=True,
    name="design_assets.batch_generate_assets",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def batch_generate_assets_task(self, product_ids: list[str], task_types: list[str]):
    """Generate design assets for multiple products in batch.

    Creates and processes design tasks for each combination of product and task type.

    Args:
        product_ids: List of product IDs to generate assets for.
        task_types: List of task type strings (e.g., ['main_image', 'detail_page']).
    """
    from .service import DesignAssetService

    logger.info(
        "Batch generation started: %d products x %d types",
        len(product_ids),
        len(task_types),
    )

    service = DesignAssetService()
    results = []

    try:
        for product_id in product_ids:
            for task_type in task_types:
                try:
                    # Create task (input_images would normally come from product data)
                    task = service.create_design_task(
                        product_id=product_id,
                        task_type=task_type,
                        input_images=[],  # Will be populated from product record
                        style_template=None,
                    )

                    # Dispatch individual processing
                    process_design_task_async.delay(task.id)

                    results.append({
                        "product_id": product_id,
                        "task_type": task_type,
                        "task_id": task.id,
                        "status": "dispatched",
                    })
                except Exception as e:
                    logger.error(
                        "Failed to create task for product=%s, type=%s: %s",
                        product_id, task_type, str(e),
                    )
                    results.append({
                        "product_id": product_id,
                        "task_type": task_type,
                        "task_id": None,
                        "status": "failed",
                        "error": str(e),
                    })
    finally:
        _run_async(service.close())

    logger.info("Batch generation dispatched: %d tasks", len(results))
    return {
        "total": len(results),
        "dispatched": sum(1 for r in results if r["status"] == "dispatched"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "tasks": results,
    }


@shared_task(
    bind=True,
    name="design_assets.regenerate_task",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def regenerate_task(self, task_id: str, params: Optional[dict] = None):
    """Regenerate a design task with different parameters.

    Reprocesses an existing task, optionally with updated style or configuration.

    Args:
        task_id: ID of the existing task to regenerate.
        params: Optional dict of parameters to override:
            - style_template: New style template ID
            - count: Number of outputs to generate
            - metadata: Additional metadata to merge
    """
    from .service import DesignAssetService, TaskStatus

    logger.info("Regeneration started: task_id=%s, params=%s", task_id, params)

    service = DesignAssetService()
    params = params or {}

    try:
        task = service.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Update task parameters if provided
        if "style_template" in params:
            task.style_template = params["style_template"]
        if "metadata" in params:
            task.metadata.update(params["metadata"])

        # Reset task state
        task.status = TaskStatus.PENDING
        task.output_images = []
        task.error_message = None
        task.completed_at = None

        # Reprocess
        result = _run_async(service.process_task(task_id))

        logger.info("Regeneration completed: task_id=%s, outputs=%d", task_id, len(result.output_images))
        return {
            "task_id": task_id,
            "status": result.status.value,
            "output_images": result.output_images,
        }
    except Exception as exc:
        logger.error("Regeneration failed: task_id=%s, error=%s", task_id, str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        _run_async(service.close())
