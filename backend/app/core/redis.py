"""Redis connection pool using redis.asyncio (aioredis successor)."""

from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_pool: Optional[aioredis.Redis] = None


async def get_redis_pool() -> aioredis.Redis:
    """Return the shared Redis connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
    return _pool


async def close_redis_pool() -> None:
    """Close the Redis connection pool (used during shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
