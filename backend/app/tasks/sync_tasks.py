"""Periodic sync tasks for orders and inventory."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine in a sync Celery context."""
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
    name="app.tasks.sync_tasks.sync_platform_orders",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
)
def sync_platform_orders(self: Any) -> dict[str, Any]:
    """Sync orders from all enabled platform providers.

    Fetches new/updated orders from connected platforms
    (Douyin Shop, Taobao, etc.) and syncs them to the local database.

    Returns:
        Sync results per platform.
    """
    logger.info("Starting platform orders sync")

    async def _execute() -> dict[str, Any]:
        from app.integrations.registry import get_provider_registry
        from app.services.ecommerce.order_service import OrderService

        # TODO: Get real database session
        # async with get_db_session() as db:
        #     order_service = OrderService(db)

        registry = get_provider_registry()
        platform_providers = registry.get_enabled("platforms")

        results: dict[str, Any] = {}

        for provider in platform_providers:
            try:
                # Fetch orders from last sync window (5 minutes + buffer)
                end_time = datetime.utcnow().isoformat()
                start_time = (
                    datetime.utcnow() - timedelta(minutes=10)
                ).isoformat()

                orders_response = await provider.get_orders(
                    start_time=start_time,
                    end_time=end_time,
                    page_size=100,
                )

                orders = orders_response.get("orders", [])
                results[provider.provider_name] = {
                    "fetched": len(orders),
                    "status": "success",
                    # TODO: Sync with order service
                    # stats = await order_service.sync_platform_orders(
                    #     provider.provider_name, orders
                    # )
                    # results[provider.provider_name].update(stats)
                }

                logger.info(
                    f"Synced {len(orders)} orders from {provider.provider_name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to sync orders from {provider.provider_name}: {e}"
                )
                results[provider.provider_name] = {
                    "status": "error",
                    "error": str(e),
                }

        return {
            "sync_time": datetime.utcnow().isoformat(),
            "platforms": results,
        }

    try:
        result = _run_async(_execute())
        logger.info(f"Order sync completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Order sync failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.tasks.sync_tasks.sync_inventory",
    bind=True,
    max_retries=3,
    soft_time_limit=180,
)
def sync_inventory(self: Any) -> dict[str, Any]:
    """Sync inventory levels to all enabled platform providers.

    Reads current inventory from the database and pushes updates
    to connected platforms to keep stock levels in sync.

    Returns:
        Sync results per platform.
    """
    logger.info("Starting inventory sync")

    async def _execute() -> dict[str, Any]:
        from app.integrations.registry import get_provider_registry

        registry = get_provider_registry()
        platform_providers = registry.get_enabled("platforms")

        # TODO: Fetch actual inventory data from database
        # async with get_db_session() as db:
        #     inventory = await db.execute(
        #         select(ProductSKU).where(ProductSKU.stock_changed == True)
        #     )
        #     inventory_data = [
        #         {"sku_id": sku.platform_sku_id, "quantity": sku.stock}
        #         for sku in inventory.scalars()
        #     ]

        # Mock inventory data for now
        inventory_data: list[dict[str, Any]] = []

        results: dict[str, Any] = {}

        for provider in platform_providers:
            try:
                sync_result = await provider.sync_inventory(inventory_data)
                results[provider.provider_name] = {
                    "status": "success",
                    **sync_result,
                }
                logger.info(
                    f"Inventory synced to {provider.provider_name}: "
                    f"{sync_result.get('synced', 0)} items"
                )
            except Exception as e:
                logger.error(
                    f"Failed to sync inventory to {provider.provider_name}: {e}"
                )
                results[provider.provider_name] = {
                    "status": "error",
                    "error": str(e),
                }

        return {
            "sync_time": datetime.utcnow().isoformat(),
            "total_items": len(inventory_data),
            "platforms": results,
        }

    try:
        result = _run_async(_execute())
        logger.info(f"Inventory sync completed")
        return result
    except Exception as exc:
        logger.error(f"Inventory sync failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.tasks.sync_tasks.check_stale_orders",
    soft_time_limit=60,
)
def check_stale_orders() -> dict[str, Any]:
    """Check for stale orders that need attention.

    Finds orders that have been in certain states too long:
    - PAID for > 24h without processing
    - PROCESSING for > 48h without shipment
    - SHIPPED for > 14 days without delivery confirmation

    Returns:
        List of stale orders requiring action.
    """
    logger.info("Checking for stale orders")

    async def _execute() -> dict[str, Any]:
        # TODO: Implement actual database queries
        # async with get_db_session() as db:
        #     now = datetime.utcnow()
        #
        #     # Orders paid > 24h ago still not processed
        #     stale_paid = await db.execute(
        #         select(Order).where(
        #             Order.status == "paid",
        #             Order.updated_at < now - timedelta(hours=24),
        #         )
        #     )
        #
        #     # Orders processing > 48h ago still not shipped
        #     stale_processing = await db.execute(
        #         select(Order).where(
        #             Order.status == "processing",
        #             Order.updated_at < now - timedelta(hours=48),
        #         )
        #     )

        return {
            "check_time": datetime.utcnow().isoformat(),
            "stale_paid": 0,
            "stale_processing": 0,
            "stale_shipped": 0,
            "notifications_sent": 0,
        }

    result = _run_async(_execute())
    logger.info(f"Stale order check completed: {result}")
    return result


@celery_app.task(
    name="app.tasks.sync_tasks.aggregate_daily_stats",
    soft_time_limit=300,
)
def aggregate_daily_stats() -> dict[str, Any]:
    """Aggregate daily statistics for dashboard.

    Computes daily metrics:
    - Order count and revenue
    - Product views and conversions
    - Platform-specific performance
    - Creative asset usage stats

    Returns:
        Aggregated daily stats.
    """
    logger.info("Starting daily stats aggregation")

    async def _execute() -> dict[str, Any]:
        yesterday = (datetime.utcnow() - timedelta(days=1)).date()

        # TODO: Implement actual aggregation queries
        # async with get_db_session() as db:
        #     order_stats = await db.execute(
        #         select(
        #             func.count(Order.id).label("count"),
        #             func.sum(Order.total).label("revenue"),
        #         ).where(
        #             func.date(Order.created_at) == yesterday
        #         )
        #     )

        stats = {
            "date": yesterday.isoformat(),
            "orders": {
                "total_count": 0,
                "total_revenue": 0.0,
                "avg_order_value": 0.0,
                "by_platform": {},
            },
            "products": {
                "new_listings": 0,
                "total_views": 0,
                "conversion_rate": 0.0,
            },
            "creative": {
                "pipelines_run": 0,
                "assets_generated": 0,
                "ai_cost_total": 0.0,
            },
            "aggregated_at": datetime.utcnow().isoformat(),
        }

        # TODO: Store stats in database
        # async with get_db_session() as db:
        #     daily_stat = DailyStat(**stats)
        #     db.add(daily_stat)
        #     await db.commit()

        return stats

    result = _run_async(_execute())
    logger.info(f"Daily stats aggregation completed for {result.get('date')}")
    return result


@celery_app.task(
    name="app.tasks.sync_tasks.sync_product_stats",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
)
def sync_product_stats(self: Any, product_ids: list[str] | None = None) -> dict[str, Any]:
    """Sync product performance stats from platforms.

    Args:
        product_ids: Optional list of product IDs. If None, syncs all active products.

    Returns:
        Sync results.
    """
    logger.info(f"Syncing product stats: {len(product_ids) if product_ids else 'all'} products")

    async def _execute() -> dict[str, Any]:
        from app.integrations.registry import get_provider_registry

        registry = get_provider_registry()
        platform_providers = registry.get_enabled("platforms")

        # TODO: Get product-platform mappings from database
        # async with get_db_session() as db:
        #     if product_ids:
        #         products = await db.execute(
        #             select(Product).where(Product.id.in_(product_ids))
        #         )
        #     else:
        #         products = await db.execute(
        #             select(Product).where(Product.status == "published")
        #         )

        synced = 0
        errors = 0

        # TODO: For each product, fetch stats from its platform
        # for product in products:
        #     for provider in platform_providers:
        #         if product.platform == provider.provider_name:
        #             stats = await provider.get_product_stats(product.external_id)
        #             # Update product stats in database

        return {
            "sync_time": datetime.utcnow().isoformat(),
            "products_synced": synced,
            "errors": errors,
        }

    try:
        result = _run_async(_execute())
        return result
    except Exception as exc:
        logger.error(f"Product stats sync failed: {exc}")
        raise self.retry(exc=exc, countdown=120)
