"""Session source monitoring tasks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.redis import get_redis_pool
from app.services.session_sources import SessionSourceService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.session_tasks.refresh_session_sources")
def refresh_session_sources() -> list[dict[str, Any]]:
    """Refresh external session source health from the local browser context."""
    return asyncio.run(_refresh_session_sources())


async def _refresh_session_sources() -> list[dict[str, Any]]:
    redis = await get_redis_pool()
    service = SessionSourceService()
    results = await service.run_scheduled_probe(redis=redis)
    logger.info("Refreshed %s session sources", len(results))
    return results
