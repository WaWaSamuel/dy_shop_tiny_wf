"""Circuit breaker pattern for external API resilience.

Opens the circuit after consecutive failures to prevent cascading damage,
and automatically resets after a configurable cooldown period.
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CircuitState(StrEnum):
    """Possible states of the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker that trips after consecutive failures.

    Args:
        name: Identifier for this circuit (e.g., API name).
        failure_threshold: Number of consecutive failures before opening.
        cooldown_seconds: Seconds to wait before transitioning to half-open.
        success_threshold: Successful calls in half-open state to fully close.
    """

    name: str
    failure_threshold: int = 5
    cooldown_seconds: float = 60.0
    success_threshold: int = 2

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        """Current circuit state, accounting for cooldown expiry."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def allow_request(self) -> bool:
        """Check whether a request is allowed through the circuit.

        Returns:
            True if the request may proceed.

        Raises:
            CircuitBreakerOpen: If the circuit is open and cooldown has not elapsed.
        """
        from app.core.exceptions import CircuitBreakerOpen

        current_state = self.state

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            return True

        # State is OPEN
        raise CircuitBreakerOpen(
            circuit_name=self.name,
            retry_after=self.cooldown_seconds - (time.time() - self._last_failure_time),
        )

    def record_success(self) -> None:
        """Record a successful call. Resets failure count or closes half-open circuit."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._reset()
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call. May trip the circuit to open state."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately re-opens
            self._state = CircuitState.OPEN
            self._success_count = 0
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def _reset(self) -> None:
        """Fully reset the circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self.state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


# Pre-configured circuit breakers for known external services
circuit_breakers: dict[str, CircuitBreaker] = {
    "douyin_api": CircuitBreaker(name="douyin_api", failure_threshold=5, cooldown_seconds=60.0),
    "alibaba_1688": CircuitBreaker(name="alibaba_1688", failure_threshold=5, cooldown_seconds=90.0),
    "chanmama": CircuitBreaker(name="chanmama", failure_threshold=5, cooldown_seconds=45.0),
    "feigua": CircuitBreaker(name="feigua", failure_threshold=5, cooldown_seconds=45.0),
    "ai_service": CircuitBreaker(name="ai_service", failure_threshold=3, cooldown_seconds=30.0),
}
