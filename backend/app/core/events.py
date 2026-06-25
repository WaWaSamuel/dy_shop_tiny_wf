"""Application startup and shutdown event handlers."""

import logging

from app.core.database import close_engines
from app.core.redis import close_redis_pool, get_redis_pool

logger = logging.getLogger(__name__)


async def on_startup() -> None:
    """Execute tasks on application startup."""
    logger.info("Starting up application...")
    # Eagerly initialize Redis pool to surface connection errors early
    redis = await get_redis_pool()
    await redis.ping()
    logger.info("Redis connection established.")
    logger.info("Startup complete.")


async def on_shutdown() -> None:
    """Execute tasks on application shutdown."""
    logger.info("Shutting down application...")
    await close_redis_pool()
    logger.info("Redis pool closed.")
    await close_engines()
    logger.info("Database engines disposed.")
    logger.info("Shutdown complete.")
