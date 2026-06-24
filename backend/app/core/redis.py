"""Redis connection pool using aioredis (redis-py async interface)."""

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None


async def get_redis_pool() -> ConnectionPool:
    """Return the shared Redis connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


async def get_redis() -> Redis:
    """Get a Redis client instance backed by the shared pool.

    Usage as a FastAPI dependency::

        @router.get("/cached")
        async def cached_endpoint(redis: Redis = Depends(get_redis)):
            value = await redis.get("my_key")
            ...
    """
    pool = await get_redis_pool()
    return Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """Gracefully close the Redis connection pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
