"""Celery tasks for asynchronous product upload operations.

Handles background processing of product uploads, batch operations,
review status polling, and auto-publishing workflows.
"""

import asyncio
import logging
import time
from typing import Any

from celery import shared_task

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

# Retry configuration
RETRY_DELAYS = [30, 60, 120, 300]  # Escalating retry delays in seconds
REVIEW_POLL_INTERVAL = 300  # 5 minutes between status checks
MAX_REVIEW_POLLS = 288  # Max 24 hours of polling (288 * 5min)


def _run_async(coro):
    """Run an async coroutine in a synchronous context (Celery worker)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_service():
    """Create a ProductUploadService instance with a database session."""
    from app.core.database import async_session_factory
    from app.modules.product_upload.service import ProductUploadService, ProductInput

    session = async_session_factory()
    service = ProductUploadService(db=session)
    return service, session


@celery_app.task(
    name="app.tasks.product_upload.upload_product",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="product_upload",
)
def upload_product_task(self, product_data: dict[str, Any]) -> dict[str, Any]:
    """Asynchronously upload a single product to 抖店.

    This task handles the full pipeline: validation, content generation,
    image upload, and submission.

    Args:
        product_data: Serialized ProductInput data.

    Returns:
        Dictionary with upload result (product_id, status, etc.).
    """
    logger.info(
        "Starting product upload task for: %s (attempt %d/%d)",
        product_data.get("name", "unknown"),
        self.request.retries + 1,
        self.max_retries + 1,
    )

    async def _execute():
        from app.modules.product_upload.service import ProductInput

        service, session = await _get_service()
        try:
            input_data = ProductInput(
                name=product_data["name"],
                description=product_data.get("description", ""),
                images=product_data.get("images", []),
                category_id=product_data.get("category_id"),
                skus=product_data.get("skus", []),
                price=product_data.get("price", 0.0),
                market_price=product_data.get("market_price", 0.0),
                stock=product_data.get("stock", 0),
                attributes=product_data.get("attributes", {}),
                keywords=product_data.get("keywords", []),
                auto_publish=product_data.get("auto_publish", False),
            )

            product = await service.create_product(input_data)
            await session.commit()

            result = {
                "success": True,
                "product_id": str(product.id),
                "douyin_product_id": product.douyin_product_id,
                "status": product.status.value,
                "name": product.name,
            }

            # Schedule review status polling if submitted
            if product.douyin_product_id:
                check_review_status_task.apply_async(
                    args=[product.douyin_product_id],
                    kwargs={"internal_product_id": str(product.id)},
                    countdown=REVIEW_POLL_INTERVAL,
                )

            return result

        except Exception as e:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error(
            "Product upload task failed for '%s': %s",
            product_data.get("name", "unknown"),
            str(exc),
        )
        # Retry with exponential backoff
        retry_delay = RETRY_DELAYS[min(self.request.retries, len(RETRY_DELAYS) - 1)]
        raise self.retry(exc=exc, countdown=retry_delay)


@celery_app.task(
    name="app.tasks.product_upload.batch_upload",
    bind=True,
    max_retries=1,
    queue="product_upload",
)
def batch_upload_task(self, products_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Batch upload multiple products with throttling.

    Dispatches individual upload tasks with rate limiting to avoid
    overwhelming the 抖店 API.

    Args:
        products_data: List of serialized ProductInput dictionaries.

    Returns:
        Dictionary with batch result summary and individual task IDs.
    """
    logger.info("Starting batch upload task for %d products", len(products_data))

    task_ids: list[dict[str, Any]] = []
    stagger_delay = 2  # Seconds between task dispatches

    for idx, product_data in enumerate(products_data):
        # Dispatch individual tasks with staggered start times
        result = upload_product_task.apply_async(
            args=[product_data],
            countdown=idx * stagger_delay,
        )
        task_ids.append(
            {
                "index": idx,
                "task_id": result.id,
                "product_name": product_data.get("name", "unknown"),
            }
        )
        logger.debug(
            "Dispatched upload task %d/%d: %s (task_id=%s)",
            idx + 1,
            len(products_data),
            product_data.get("name", "unknown"),
            result.id,
        )

    return {
        "total": len(products_data),
        "dispatched": len(task_ids),
        "tasks": task_ids,
    }


@celery_app.task(
    name="app.tasks.product_upload.check_review_status",
    bind=True,
    max_retries=MAX_REVIEW_POLLS,
    default_retry_delay=REVIEW_POLL_INTERVAL,
    queue="product_upload",
)
def check_review_status_task(
    self,
    douyin_product_id: str,
    internal_product_id: str | None = None,
) -> dict[str, Any]:
    """Poll 抖店 for product review status until a terminal state is reached.

    Continues polling every 5 minutes until the product is approved,
    rejected, or the maximum poll count is reached.

    Args:
        douyin_product_id: The 抖店 product ID to check.
        internal_product_id: Optional internal product UUID for DB updates.

    Returns:
        Dictionary with the final status.
    """
    logger.info(
        "Checking review status for product %s (poll %d/%d)",
        douyin_product_id,
        self.request.retries + 1,
        MAX_REVIEW_POLLS,
    )

    async def _execute():
        from app.core.database import async_session_factory
        from app.models.product import Product, ProductStatus
        from app.modules.product_upload.service import ProductUploadService

        session = async_session_factory()
        service = ProductUploadService(db=session)

        try:
            status = await service.check_product_status(douyin_product_id)

            # Update internal database if we have the product ID
            if internal_product_id:
                from sqlalchemy import select, update
                from sqlalchemy.dialects.postgresql import UUID
                import uuid

                stmt = (
                    select(Product)
                    .where(Product.id == uuid.UUID(internal_product_id))
                )
                result = await session.execute(stmt)
                product = result.scalar_one_or_none()

                if product:
                    product.status = status
                    if status == ProductStatus.APPROVED:
                        from datetime import datetime
                        product.listing_approved_at = datetime.utcnow()
                    await session.commit()

            return status

        except Exception as e:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        status = _run_async(_execute())
    except Exception as exc:
        logger.error(
            "Review status check failed for %s: %s",
            douyin_product_id,
            str(exc),
        )
        raise self.retry(exc=exc, countdown=REVIEW_POLL_INTERVAL)

    # Terminal states - stop polling
    from app.models.product import ProductStatus

    terminal_states = {
        ProductStatus.APPROVED,
        ProductStatus.REJECTED,
        ProductStatus.ONLINE,
        ProductStatus.OFFLINE,
    }

    if status in terminal_states:
        logger.info(
            "Product %s reached terminal status: %s",
            douyin_product_id,
            status.value,
        )

        # Auto-publish if approved
        if status == ProductStatus.APPROVED:
            auto_publish_task.apply_async(
                args=[douyin_product_id],
                kwargs={"internal_product_id": internal_product_id},
                countdown=10,  # Small delay before publishing
            )

        return {
            "product_id": douyin_product_id,
            "status": status.value,
            "polls_completed": self.request.retries + 1,
        }

    # Not terminal - schedule next poll
    raise self.retry(countdown=REVIEW_POLL_INTERVAL)


@celery_app.task(
    name="app.tasks.product_upload.auto_publish",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="product_upload",
)
def auto_publish_task(
    self,
    douyin_product_id: str,
    internal_product_id: str | None = None,
) -> dict[str, Any]:
    """Automatically publish a product after review approval.

    Called by check_review_status_task when a product transitions
    to the APPROVED state.

    Args:
        douyin_product_id: The 抖店 product ID to publish.
        internal_product_id: Optional internal product UUID for DB updates.

    Returns:
        Dictionary indicating publish success or failure.
    """
    logger.info("Auto-publishing product %s", douyin_product_id)

    async def _execute():
        from app.core.database import async_session_factory
        from app.models.product import Product, ProductStatus
        from app.modules.product_upload.service import ProductUploadService

        session = async_session_factory()
        service = ProductUploadService(db=session)

        try:
            success = await service.publish_product(douyin_product_id)

            if success and internal_product_id:
                from sqlalchemy import select
                import uuid

                stmt = (
                    select(Product)
                    .where(Product.id == uuid.UUID(internal_product_id))
                )
                result = await session.execute(stmt)
                product = result.scalar_one_or_none()

                if product:
                    product.status = ProductStatus.ONLINE
                    await session.commit()

            return success

        except Exception as e:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        success = _run_async(_execute())
    except Exception as exc:
        logger.error(
            "Auto-publish failed for product %s: %s",
            douyin_product_id,
            str(exc),
        )
        raise self.retry(exc=exc, countdown=60)

    return {
        "product_id": douyin_product_id,
        "published": success,
    }
