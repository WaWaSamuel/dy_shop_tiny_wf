"""Dependency injection utilities for API endpoints."""

from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_read_session, get_write_session
from app.core.redis import get_redis_pool
from app.core.security import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)
_DEBUG_ECOMMERCE_DEMO_USER_ID = "demo-ecommerce-user"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a write-capable database session."""
    async for session in get_write_session():
        yield session


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a read-only database session."""
    async for session in get_read_session():
        yield session


async def get_redis() -> aioredis.Redis:
    """Provide a Redis connection."""
    return await get_redis_pool()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Decode the bearer token and return the current user payload.

    Raises:
        HTTPException 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    return payload


async def get_current_user_id(
    user: dict = Depends(get_current_user),
) -> str:
    """Extract user ID from the token payload."""
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return user_id


async def get_current_ecommerce_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """Return the current ecommerce user id, with debug-only fallback for local mocking."""
    settings = get_settings()
    if credentials is None and settings.DEBUG:
        return _DEBUG_ECOMMERCE_DEMO_USER_ID

    user = await get_current_user(credentials)
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return user_id
