"""Security utilities for 抖店 (Douyin Shop) API authentication.

Implements HMAC-SHA256 request signing per the Douyin Open Platform specification,
and token refresh logic to maintain long-lived access.
"""

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import settings

_DOUYIN_TOKEN_URL = "https://openapi-fxg.jinritemai.com/token/refresh"


def sign_request(
    method: str,
    path: str,
    params: dict[str, Any],
    body: str = "",
    timestamp: int | None = None,
) -> dict[str, str]:
    """Generate HMAC-SHA256 signature headers for a 抖店 API request.

    Args:
        method: HTTP method (GET, POST, etc.).
        path: API path (e.g., "/order/list").
        params: Query parameters to include in signing.
        body: Request body string (JSON-serialized for POST requests).
        timestamp: Unix timestamp; defaults to current time.

    Returns:
        Dictionary of headers to attach to the outgoing request, including
        the computed signature, app key, and timestamp.
    """
    if timestamp is None:
        timestamp = int(time.time())

    # Sort parameters alphabetically by key
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if v is not None
    )

    # Construct the string to sign
    sign_string = f"{settings.DOUYIN_APP_KEY}{method}{path}{sorted_params}{body}{timestamp}"

    # Compute HMAC-SHA256
    signature = hmac.new(
        settings.DOUYIN_APP_SECRET.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "app_key": settings.DOUYIN_APP_KEY,
        "timestamp": str(timestamp),
        "sign": signature,
        "sign_method": "hmac-sha256",
    }


async def refresh_access_token() -> dict[str, str]:
    """Refresh the Douyin access token using the stored refresh token.

    Returns:
        Dictionary containing the new access_token and refresh_token.

    Raises:
        DouyinAPIError: If the token refresh request fails.
    """
    from app.core.exceptions import DouyinAPIError

    payload = {
        "app_id": settings.DOUYIN_APP_KEY,
        "app_secret": settings.DOUYIN_APP_SECRET,
        "refresh_token": settings.DOUYIN_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_DOUYIN_TOKEN_URL, json=payload)

    if response.status_code != 200:
        raise DouyinAPIError(
            message="Token refresh request failed",
            status_code=response.status_code,
            response_body=response.text,
        )

    data = response.json()
    if data.get("err_no") != 0:
        raise DouyinAPIError(
            message=f"Token refresh error: {data.get('message', 'unknown')}",
            status_code=response.status_code,
            response_body=response.text,
        )

    token_data = data.get("data", {})
    return {
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_in": token_data.get("expires_in", 0),
    }
