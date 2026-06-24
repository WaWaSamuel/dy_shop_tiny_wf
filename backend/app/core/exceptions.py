"""Custom exception classes for the Douyin Shop Automation platform."""

from typing import Any


class DouyinAPIError(Exception):
    """Raised when a Douyin (抖店) API request fails.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code from the upstream response.
        response_body: Raw response body for debugging.
    """

    def __init__(
        self,
        message: str = "Douyin API request failed",
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"DouyinAPIError(message={self.message!r}, "
            f"status_code={self.status_code})"
        )


class RateLimitExceeded(Exception):
    """Raised when a rate-limit bucket is exhausted.

    Attributes:
        category: The API category that was rate-limited.
        retry_after: Suggested wait time in seconds before retrying.
    """

    def __init__(
        self,
        category: str,
        retry_after: float = 1.0,
    ) -> None:
        self.category = category
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for '{category}'. Retry after {retry_after:.1f}s."
        )


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is in the open state.

    Attributes:
        circuit_name: Name of the tripped circuit breaker.
        retry_after: Estimated seconds until the circuit transitions to half-open.
    """

    def __init__(
        self,
        circuit_name: str,
        retry_after: float = 0.0,
    ) -> None:
        self.circuit_name = circuit_name
        self.retry_after = max(0.0, retry_after)
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Retry after ~{self.retry_after:.1f}s."
        )


class ValidationError(Exception):
    """Raised for domain-level validation failures (distinct from Pydantic's).

    Attributes:
        field: The field that failed validation.
        detail: Explanation of the validation failure.
        value: The rejected value (optional, omitted from logs if sensitive).
    """

    def __init__(
        self,
        field: str,
        detail: str,
        value: Any = None,
    ) -> None:
        self.field = field
        self.detail = detail
        self.value = value
        super().__init__(f"Validation failed on '{field}': {detail}")
