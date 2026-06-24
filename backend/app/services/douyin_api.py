"""Unified 抖店 (Douyin Shop) API client.

Handles HMAC-SHA256 request signing, automatic token refresh,
rate limiting, error retry with exponential backoff, and circuit
breaker integration for fault tolerance.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.circuit_breaker import CircuitBreaker, circuit_breakers
from app.core.config import settings
from app.core.exceptions import DouyinAPIError, RateLimitExceeded

logger = logging.getLogger(__name__)

# 抖店 Open API base URL
DOUYIN_API_BASE = "https://openapi-fxg.jinritemai.com"

# Token refresh buffer (10 minutes before expiry)
TOKEN_REFRESH_BUFFER_SECONDS = 600

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class DouyinAPIClient:
    """Unified client for the 抖店 Open API.

    Features:
    - HMAC-SHA256 request signing per Douyin specification
    - Automatic access token refresh with 10-min buffer
    - Per-endpoint rate limiting via token bucket
    - Exponential backoff retry on transient failures
    - Circuit breaker for cascading failure prevention

    Usage:
        client = DouyinAPIClient()
        products = await client.get("/product/listV2", params={"page": 1, "size": 20})
        await client.close()
    """

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        base_url: str = DOUYIN_API_BASE,
    ) -> None:
        self._app_key = app_key or settings.DOUYIN_APP_KEY
        self._app_secret = app_secret or settings.DOUYIN_APP_SECRET
        self._access_token = access_token or settings.DOUYIN_ACCESS_TOKEN
        self._refresh_token = refresh_token or settings.DOUYIN_REFRESH_TOKEN
        self._base_url = base_url.rstrip("/")
        self._token_expires_at: float = 0.0

        # HTTP client with connection pooling
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        # Circuit breaker
        self._circuit_breaker: CircuitBreaker = circuit_breakers.get(
            "douyin_api",
            CircuitBreaker(name="douyin_api", failure_threshold=5, cooldown_seconds=60.0),
        )

        # Rate limiter (lazy init to avoid import cycles)
        self._rate_limiter = None

    async def _get_rate_limiter(self):
        """Lazily initialize the rate limiter."""
        if self._rate_limiter is None:
            from app.core.rate_limiter import TokenBucketRateLimiter
            from app.core.redis import get_redis

            redis = await get_redis()
            self._rate_limiter = TokenBucketRateLimiter(redis=redis)
        return self._rate_limiter

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict:
        """Make a signed GET request to the Douyin API.

        Args:
            endpoint: API endpoint path (e.g., "/product/listV2").
            params: Query parameters.

        Returns:
            Parsed JSON response data.

        Raises:
            DouyinAPIError: On API error response.
            RateLimitExceeded: When rate limit is exhausted.
            CircuitBreakerOpen: When circuit breaker is open.
        """
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict:
        """Make a signed POST request to the Douyin API.

        Args:
            endpoint: API endpoint path (e.g., "/product/createV2").
            data: JSON request body.

        Returns:
            Parsed JSON response data.

        Raises:
            DouyinAPIError: On API error response.
            RateLimitExceeded: When rate limit is exhausted.
            CircuitBreakerOpen: When circuit breaker is open.
        """
        return await self._request("POST", endpoint, data=data)

    async def upload_file(self, endpoint: str, file_path: str) -> dict:
        """Upload a file to the Douyin API.

        Args:
            endpoint: Upload endpoint path (e.g., "/product/uploadImg").
            file_path: Local path to the file to upload.

        Returns:
            Parsed JSON response with uploaded file info.

        Raises:
            DouyinAPIError: On API error response.
            FileNotFoundError: If file_path doesn't exist.
        """
        import aiofiles

        self._circuit_breaker.allow_request()
        await self._ensure_token_valid()

        # Prepare multipart upload
        timestamp = str(int(time.time()))
        sign_params = {
            "app_key": self._app_key,
            "timestamp": timestamp,
            "v": "2",
            "method": endpoint.strip("/").replace("/", "."),
        }
        sign_params["sign"] = self._generate_sign(sign_params)
        sign_params["access_token"] = self._access_token

        try:
            async with aiofiles.open(file_path, "rb") as f:
                file_content = await f.read()

            response = await self._client.post(
                endpoint,
                params=sign_params,
                files={"file": ("upload", file_content)},
            )

            result = response.json()

            if response.status_code != 200 or result.get("err_no", 0) != 0:
                self._circuit_breaker.record_failure()
                raise DouyinAPIError(
                    message=result.get("message", "Upload failed"),
                    status_code=response.status_code,
                    response_body=response.text,
                )

            self._circuit_breaker.record_success()
            return result.get("data", result)

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            self._circuit_breaker.record_failure()
            raise DouyinAPIError(
                message=f"File upload network error: {exc}",
                status_code=None,
            ) from exc

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    # -------------------------------------------------------------------------
    # Request signing and execution
    # -------------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict:
        """Execute a signed API request with retry and circuit breaker.

        Args:
            method: HTTP method (GET or POST).
            endpoint: API endpoint path.
            params: Query parameters for GET requests.
            data: JSON body for POST requests.

        Returns:
            Parsed JSON response data.
        """
        # Circuit breaker check
        self._circuit_breaker.allow_request()

        # Rate limiting
        rate_limiter = await self._get_rate_limiter()
        await rate_limiter.acquire("douyin_default")

        # Ensure token is valid
        await self._ensure_token_valid()

        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                result = await self._execute_request(method, endpoint, params, data)
                self._circuit_breaker.record_success()
                return result
            except DouyinAPIError as exc:
                last_exc = exc
                # Don't retry on client errors (4xx)
                if exc.status_code and 400 <= exc.status_code < 500:
                    self._circuit_breaker.record_failure()
                    raise
                # Retry on server errors
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "[DouyinAPI] Retrying %s %s (attempt %d/%d, delay %.1fs): %s",
                        method, endpoint, attempt + 1, MAX_RETRIES, delay, exc.message,
                    )
                    import asyncio
                    await asyncio.sleep(delay)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "[DouyinAPI] Network error, retrying %s %s (attempt %d/%d): %s",
                        method, endpoint, attempt + 1, MAX_RETRIES, str(exc),
                    )
                    import asyncio
                    await asyncio.sleep(delay)

        # All retries exhausted
        self._circuit_breaker.record_failure()
        if isinstance(last_exc, DouyinAPIError):
            raise last_exc
        raise DouyinAPIError(
            message=f"Request failed after {MAX_RETRIES} attempts: {last_exc}",
        )

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict:
        """Execute a single signed request (no retry logic)."""
        timestamp = str(int(time.time()))

        # Build signing parameters
        sign_params = {
            "app_key": self._app_key,
            "timestamp": timestamp,
            "v": "2",
            "method": endpoint.strip("/").replace("/", "."),
        }

        # Include business params in signature for POST
        if method == "POST" and data:
            import json
            sign_params["param_json"] = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

        sign_params["sign"] = self._generate_sign(sign_params)
        sign_params["access_token"] = self._access_token

        # Make the request
        if method == "GET":
            query_params = {**sign_params, **(params or {})}
            response = await self._client.get(endpoint, params=query_params)
        else:
            import json
            response = await self._client.post(
                endpoint,
                params=sign_params,
                json=data or {},
            )

        # Parse response
        result = response.json()

        # Check for API-level errors
        err_no = result.get("err_no", 0)
        if response.status_code != 200 or err_no != 0:
            raise DouyinAPIError(
                message=result.get("message", f"API error {err_no}"),
                status_code=response.status_code,
                response_body=response.text,
            )

        return result.get("data", result)

    def _generate_sign(self, params: dict[str, str]) -> str:
        """Generate HMAC-SHA256 signature for API request.

        The signing algorithm:
        1. Sort parameters alphabetically by key
        2. Concatenate as key=value pairs (no separator)
        3. Wrap with app_secret: secret + sorted_params + secret
        4. HMAC-SHA256 with app_secret as key
        5. Return hex digest

        Args:
            params: Parameters to include in signature.

        Returns:
            Hex-encoded HMAC-SHA256 signature string.
        """
        # Sort and concatenate
        sorted_items = sorted(params.items(), key=lambda x: x[0])
        param_str = "".join(f"{k}{v}" for k, v in sorted_items)

        # Wrap with secret
        sign_string = f"{self._app_secret}{param_str}{self._app_secret}"

        # HMAC-SHA256
        signature = hmac.new(
            self._app_secret.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return signature

    # -------------------------------------------------------------------------
    # Token management
    # -------------------------------------------------------------------------

    async def _ensure_token_valid(self) -> None:
        """Check and refresh access token if expired or near expiry.

        Refreshes the token if it will expire within TOKEN_REFRESH_BUFFER_SECONDS.
        """
        now = time.time()

        # If token_expires_at is 0, we haven't set it yet; assume valid for now
        if self._token_expires_at == 0:
            return

        if now >= (self._token_expires_at - TOKEN_REFRESH_BUFFER_SECONDS):
            await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token.

        Updates internal state with new access_token and expiry.
        """
        logger.info("[DouyinAPI] Refreshing access token")

        try:
            response = await self._client.get(
                "/token/refresh",
                params={
                    "app_key": self._app_key,
                    "app_secret": self._app_secret,
                    "refresh_token": self._refresh_token,
                },
            )

            result = response.json()

            if result.get("err_no", 0) != 0:
                raise DouyinAPIError(
                    message=f"Token refresh failed: {result.get('message')}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            data = result.get("data", {})
            self._access_token = data.get("access_token", self._access_token)
            self._refresh_token = data.get("refresh_token", self._refresh_token)

            # Set expiry (Douyin tokens typically last 12-24 hours)
            expires_in = data.get("expires_in", 86400)
            self._token_expires_at = time.time() + expires_in

            logger.info(
                "[DouyinAPI] Token refreshed, expires in %d seconds", expires_in
            )

        except DouyinAPIError:
            raise
        except Exception as exc:
            logger.error("[DouyinAPI] Token refresh error: %s", exc)
            raise DouyinAPIError(
                message=f"Token refresh network error: {exc}",
            ) from exc
