"""Redis cache decorator utility."""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Redis client placeholder - initialized at application startup
_redis_client: Any = None


def init_redis(redis_url: str = "redis://localhost:6379/0") -> None:
    """Initialize the Redis client.

    Should be called during application startup.

    Args:
        redis_url: Redis connection URL.
    """
    global _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info(f"Redis client initialized: {redis_url}")
    except ImportError:
        logger.warning(
            "redis package not installed. Cache will be disabled. "
            "Install with: pip install redis[hiredis]"
        )
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")


def get_redis() -> Any:
    """Get the Redis client instance."""
    return _redis_client


def _build_cache_key(prefix: str, func: Callable, args: tuple, kwargs: dict) -> str:
    """Build a unique cache key from function call parameters."""
    # Create a stable hash of the arguments
    key_parts = [prefix, func.__module__, func.__qualname__]

    # Include positional args (skip 'self' if present)
    serializable_args = []
    for arg in args:
        if hasattr(arg, "__dict__") and not isinstance(arg, (str, int, float, bool)):
            # Skip non-serializable objects (like self, db sessions)
            continue
        serializable_args.append(str(arg))

    # Include keyword args
    serializable_kwargs = {
        k: str(v) for k, v in sorted(kwargs.items())
        if not hasattr(v, "__dict__") or isinstance(v, (str, int, float, bool))
    }

    key_data = json.dumps(
        {"args": serializable_args, "kwargs": serializable_kwargs},
        sort_keys=True,
        default=str,
    )
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    key_parts.append(key_hash)

    return ":".join(key_parts)


def cache(
    *,
    prefix: str = "cache",
    ttl: int = 300,
    key_builder: Optional[Callable[..., str]] = None,
    skip_cache_if: Optional[Callable[..., bool]] = None,
) -> Callable:
    """Async Redis cache decorator.

    Caches the return value of an async function in Redis.
    If the value is in cache, returns it without calling the function.

    Args:
        prefix: Cache key prefix for namespacing.
        ttl: Time-to-live in seconds (default: 5 minutes).
        key_builder: Optional custom key builder function.
        skip_cache_if: Optional function that returns True to skip cache.

    Returns:
        Decorated function.

    Example:
        @cache(prefix="products", ttl=60)
        async def get_product(product_id: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip cache if Redis not available
            if _redis_client is None:
                return await func(*args, **kwargs)

            # Check skip condition
            if skip_cache_if and skip_cache_if(*args, **kwargs):
                return await func(*args, **kwargs)

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _build_cache_key(prefix, func, args, kwargs)

            # Try to get from cache
            try:
                cached_value = await _redis_client.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return json.loads(cached_value)
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

            # Cache miss - call the function
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                serialized = json.dumps(result, default=str)
                await _redis_client.setex(cache_key, ttl, serialized)
            except (TypeError, ValueError) as e:
                logger.warning(f"Cache write error (serialization): {e}")
            except Exception as e:
                logger.warning(f"Cache write error for {cache_key}: {e}")

            return result

        # Attach cache management methods
        wrapper.cache_prefix = prefix  # type: ignore[attr-defined]

        async def invalidate(*args: Any, **kwargs: Any) -> bool:
            """Manually invalidate cached value for given args."""
            if _redis_client is None:
                return False
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _build_cache_key(prefix, func, args, kwargs)
            try:
                deleted = await _redis_client.delete(cache_key)
                return bool(deleted)
            except Exception as e:
                logger.warning(f"Cache invalidate error: {e}")
                return False

        wrapper.invalidate = invalidate  # type: ignore[attr-defined]

        return wrapper
    return decorator


async def invalidate_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "cache:products:*").

    Returns:
        Number of keys deleted.
    """
    if _redis_client is None:
        return 0

    try:
        keys = []
        async for key in _redis_client.scan_iter(match=pattern, count=100):
            keys.append(key)

        if keys:
            deleted = await _redis_client.delete(*keys)
            logger.info(f"Invalidated {deleted} cache keys matching '{pattern}'")
            return int(deleted)
        return 0
    except Exception as e:
        logger.error(f"Cache pattern invalidation error: {e}")
        return 0


async def cache_get(key: str) -> Optional[Any]:
    """Direct cache get operation.

    Args:
        key: Cache key.

    Returns:
        Cached value or None.
    """
    if _redis_client is None:
        return None
    try:
        value = await _redis_client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """Direct cache set operation.

    Args:
        key: Cache key.
        value: Value to cache (must be JSON serializable).
        ttl: Time-to-live in seconds.

    Returns:
        True if successful.
    """
    if _redis_client is None:
        return False
    try:
        serialized = json.dumps(value, default=str)
        await _redis_client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"Cache set error: {e}")
        return False
