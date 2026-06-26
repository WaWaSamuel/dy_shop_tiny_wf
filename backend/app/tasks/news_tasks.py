"""Periodic tasks for news digest aggregation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.redis import get_redis_pool
from app.services.news_aggregator import NewsAggregationService
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
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.news_tasks.refresh_news_digest",
    bind=True,
    max_retries=2,
    soft_time_limit=180,
)
def refresh_news_digest(self: Any) -> dict[str, Any]:
    """Refresh the latest completed overnight news digest."""

    async def _execute() -> dict[str, Any]:
        redis = await get_redis_pool()
        service = NewsAggregationService()
        return await service.get_digest(redis=redis, force_refresh=True)

    try:
        result = _run_async(_execute())
        logger.info("News digest refreshed: %s articles", result.get("total_articles"))
        return result
    except Exception as exc:
        logger.error("News digest refresh failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
