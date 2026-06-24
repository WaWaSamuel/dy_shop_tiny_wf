"""Token-bucket rate limiter for external API calls.

Supports configurable limits per API category (e.g., Douyin, 1688, Chanmama).
Uses Redis for distributed state so that multiple workers share the same bucket.
"""

import time
from dataclasses import dataclass, field

from redis.asyncio import Redis


@dataclass(slots=True)
class RateLimitConfig:
    """Configuration for a single rate-limit bucket.

    Attributes:
        max_tokens: Maximum burst capacity (requests).
        refill_rate: Tokens added per second.
    """

    max_tokens: int
    refill_rate: float


# Pre-defined rate limit profiles per API category.
# Adjust these based on each platform's documented quotas.
RATE_LIMIT_PROFILES: dict[str, RateLimitConfig] = {
    "douyin_default": RateLimitConfig(max_tokens=40, refill_rate=40 / 60),
    "douyin_order": RateLimitConfig(max_tokens=80, refill_rate=80 / 60),
    "douyin_product": RateLimitConfig(max_tokens=60, refill_rate=60 / 60),
    "alibaba_1688": RateLimitConfig(max_tokens=100, refill_rate=100 / 60),
    "chanmama": RateLimitConfig(max_tokens=120, refill_rate=120 / 60),
    "feigua": RateLimitConfig(max_tokens=200, refill_rate=200 / 60),
    "ai_service": RateLimitConfig(max_tokens=60, refill_rate=60 / 60),
}


@dataclass
class TokenBucketRateLimiter:
    """Distributed token-bucket rate limiter backed by Redis.

    Each API category maintains its own bucket identified by a Redis key.
    """

    redis: Redis
    key_prefix: str = "rate_limit"

    async def acquire(self, category: str, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the bucket.

        Args:
            category: The API category key (must exist in RATE_LIMIT_PROFILES).
            tokens: Number of tokens to consume (default 1 per request).

        Returns:
            True if tokens were consumed successfully; False if rate limit exceeded.

        Raises:
            RateLimitExceeded: When no tokens are available and caller should back off.
        """
        from app.core.exceptions import RateLimitExceeded

        config = RATE_LIMIT_PROFILES.get(category)
        if config is None:
            # Unknown category: allow by default but log a warning
            return True

        key = f"{self.key_prefix}:{category}"
        now = time.time()

        # Atomic Lua script for token bucket logic
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1])
        local last_refill = tonumber(bucket[2])

        if tokens == nil then
            tokens = max_tokens
            last_refill = now
        end

        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        local new_tokens = elapsed * refill_rate
        tokens = math.min(max_tokens, tokens + new_tokens)
        last_refill = now

        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, 120)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, 120)
            return 0
        end
        """

        result = await self.redis.eval(
            lua_script,
            1,
            key,
            str(config.max_tokens),
            str(config.refill_rate),
            str(now),
            str(tokens),
        )

        if result == 0:
            raise RateLimitExceeded(
                category=category,
                retry_after=tokens / config.refill_rate,
            )

        return True

    async def get_remaining(self, category: str) -> int:
        """Get approximate remaining tokens for a category."""
        config = RATE_LIMIT_PROFILES.get(category)
        if config is None:
            return -1

        key = f"{self.key_prefix}:{category}"
        bucket = await self.redis.hmget(key, "tokens", "last_refill")

        if bucket[0] is None:
            return config.max_tokens

        current_tokens = float(bucket[0])
        last_refill = float(bucket[1])
        elapsed = time.time() - last_refill
        refilled = elapsed * config.refill_rate
        available = min(config.max_tokens, current_tokens + refilled)

        return int(available)
