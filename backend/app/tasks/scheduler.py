"""Celery beat schedule configuration for all modules.

Combines schedules from all 4 modules into a single unified beat config:
- 06:00 - Product Discovery daily scan
- 07:00 - Design Assets: generate images for approved candidates
- 08:00 - Product Upload: batch upload new products with assets
- Every 5 min - Feedback: poll reviews
- Every 3 min - Feedback: poll after-sale tickets
- 12:00, 18:00 - Status report digest
- 22:00 - Feedback: batch process unanswered
- 23:00 - Daily metrics report
"""

import logging

from celery.schedules import crontab

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


# Unified beat schedule combining all module schedules
BEAT_SCHEDULE: dict = {
    # =========================================================================
    # DISCOVERY MODULE (06:00)
    # =========================================================================
    "discovery-daily-scan": {
        "task": "app.tasks.scheduler.task_discovery_daily_scan",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "discovery"},
        "kwargs": {},
    },

    # =========================================================================
    # DESIGN ASSETS MODULE (07:00)
    # =========================================================================
    "design-generate-for-approved": {
        "task": "app.tasks.scheduler.task_design_generate_for_approved",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "design_assets"},
        "kwargs": {},
    },

    # =========================================================================
    # PRODUCT UPLOAD MODULE (08:00)
    # =========================================================================
    "product-upload-batch-new": {
        "task": "app.tasks.scheduler.task_product_upload_batch",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "product_upload"},
        "kwargs": {},
    },

    # =========================================================================
    # FEEDBACK MODULE (high frequency polling)
    # =========================================================================
    "feedback-poll-reviews-every-5min": {
        "task": "app.tasks.feedback.poll_reviews",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"queue": "feedback"},
    },
    "feedback-poll-after-sale-every-3min": {
        "task": "app.tasks.feedback.poll_after_sale",
        "schedule": 180.0,  # Every 3 minutes
        "options": {"queue": "feedback"},
    },
    "feedback-batch-process-unanswered": {
        "task": "app.tasks.feedback.batch_process_unanswered",
        "schedule": crontab(hour=22, minute=0),
        "options": {"queue": "feedback"},
    },

    # =========================================================================
    # FULFILLMENT MODULE (order polling fallback + logistics refresh)
    # =========================================================================
    "fulfillment-poll-new-orders-every-10min": {
        "task": "app.modules.fulfillment.tasks.poll_new_orders_task",
        "schedule": 600.0,  # Every 10 minutes (webhook is the primary path)
        "options": {"queue": "fulfillment"},
    },
    "fulfillment-refresh-logistics-every-30min": {
        "task": "app.modules.fulfillment.tasks.refresh_active_logistics_task",
        "schedule": 1800.0,  # Every 30 minutes
        "options": {"queue": "fulfillment"},
    },

    # =========================================================================
    # STATUS & REPORTING
    # =========================================================================
    "status-report-midday": {
        "task": "app.tasks.scheduler.task_status_digest",
        "schedule": crontab(hour=12, minute=0),
        "options": {"queue": "discovery"},
        "kwargs": {},
    },
    "status-report-evening": {
        "task": "app.tasks.scheduler.task_status_digest",
        "schedule": crontab(hour=18, minute=0),
        "options": {"queue": "discovery"},
        "kwargs": {},
    },
    "daily-metrics-report": {
        "task": "app.tasks.scheduler.task_daily_metrics_report",
        "schedule": crontab(hour=23, minute=0),
        "options": {"queue": "discovery"},
        "kwargs": {},
    },
}


def register_beat_schedule() -> None:
    """Register the unified beat schedule with the Celery app.

    Call this at app startup to replace per-module schedule registration
    with the central configuration.
    """
    celery_app.conf.beat_schedule = BEAT_SCHEDULE
    logger.info(
        "Registered unified beat schedule with %d entries", len(BEAT_SCHEDULE)
    )


# ---------------------------------------------------------------------------
# Celery task definitions for scheduled operations
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.tasks.scheduler.task_discovery_daily_scan",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="discovery",
)
def task_discovery_daily_scan(self) -> dict:
    """06:00 - Run the daily product discovery scan.

    Delegates to the discovery module's daily_scan_task.
    """
    logger.info("[Scheduler] Triggering discovery daily scan")
    from app.modules.discovery.tasks import daily_scan_task

    try:
        result = daily_scan_task()
        logger.info("[Scheduler] Discovery scan completed: %s", result)
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("[Scheduler] Discovery scan failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.scheduler.task_design_generate_for_approved",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="design_assets",
)
def task_design_generate_for_approved(self) -> dict:
    """07:00 - Generate design images for approved candidates.

    Queries for approved candidates that don't yet have design assets
    and triggers batch generation.
    """
    import asyncio

    logger.info("[Scheduler] Triggering design asset generation for approved candidates")

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.models.discovery import SourceCandidate, SourceCandidateStatus
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Find approved candidates needing assets
            stmt = (
                select(SourceCandidate)
                .where(SourceCandidate.status == SourceCandidateStatus.APPROVED)
                .limit(20)
            )
            result = await db.execute(stmt)
            candidates = list(result.scalars().all())

            if not candidates:
                return {"status": "no_candidates", "count": 0}

            # Dispatch batch design task
            product_ids = [str(c.trending_product_id) for c in candidates]

            from app.modules.design_assets.tasks import batch_generate_assets_task

            batch_generate_assets_task.delay(
                product_ids=product_ids,
                task_types=["main_image", "detail_page"],
            )

            return {
                "status": "dispatched",
                "candidates_count": len(candidates),
                "product_ids": product_ids,
            }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
        logger.info("[Scheduler] Design generation dispatched: %s", result)
        return result
    except Exception as exc:
        logger.error("[Scheduler] Design generation failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.scheduler.task_product_upload_batch",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="product_upload",
)
def task_product_upload_batch(self) -> dict:
    """08:00 - Batch upload new products that have completed design assets.

    Finds products with completed design assets that haven't been uploaded yet.
    """
    import asyncio

    logger.info("[Scheduler] Triggering batch product upload")

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.models.product import Product, ProductStatus
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Find products in DRAFT status with completed assets
            stmt = (
                select(Product)
                .where(Product.status == ProductStatus.DRAFT)
                .limit(20)
            )
            result = await db.execute(stmt)
            products = list(result.scalars().all())

            if not products:
                return {"status": "no_products", "count": 0}

            # Build product data for batch upload
            products_data = []
            for product in products:
                products_data.append({
                    "name": product.name,
                    "description": product.description or "",
                    "images": product.images or [],
                    "category_id": product.category_id,
                    "price": float(product.price) if product.price else 0.0,
                    "stock": product.stock or 0,
                    "auto_publish": True,
                })

            from app.modules.product_upload.tasks import batch_upload_task

            batch_upload_task.delay(products_data)

            return {
                "status": "dispatched",
                "products_count": len(products_data),
            }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
        logger.info("[Scheduler] Batch upload dispatched: %s", result)
        return result
    except Exception as exc:
        logger.error("[Scheduler] Batch upload failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.scheduler.task_status_digest",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    queue="discovery",
)
def task_status_digest(self) -> dict:
    """12:00 & 18:00 - Generate and send a status report digest."""
    logger.info("[Scheduler] Generating status digest")

    try:
        from app.tasks.workflow import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator()
        digest = orchestrator.generate_status_digest()
        logger.info("[Scheduler] Status digest generated: %s", digest)
        return {"status": "success", "digest": digest}
    except Exception as exc:
        logger.error("[Scheduler] Status digest failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.scheduler.task_daily_metrics_report",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    queue="discovery",
)
def task_daily_metrics_report(self) -> dict:
    """23:00 - Generate the full daily metrics report."""
    logger.info("[Scheduler] Generating daily metrics report")

    try:
        from app.tasks.workflow import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator()
        report = orchestrator.generate_daily_report()
        logger.info("[Scheduler] Daily report generated: %s", report)
        return {"status": "success", "report": report}
    except Exception as exc:
        logger.error("[Scheduler] Daily report failed: %s", exc)
        raise self.retry(exc=exc)
