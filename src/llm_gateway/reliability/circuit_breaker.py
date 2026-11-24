import threading
import time
from enum import Enum
from typing import Callable, Optional


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Raised when a request is rejected because the circuit is OPEN."""

    def __init__(self, provider: str, retry_after: float):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker OPEN for {provider}. Retry after {retry_after:.1f}s")


class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern with three states: CLOSED, OPEN, HALF_OPEN.
    
    State transitions:
    - CLOSED -> OPEN: When failure_count >= failure_threshold
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: On successful probe request
    - HALF_OPEN -> OPEN: On failed probe request
    
    In HALF_OPEN state, only max_half_open_probes concurrent requests are allowed.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        max_half_open_probes: int = 3,
        clock: Optional[Callable[[], float]] = None,
        name: str = "unknown",
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_half_open_probes = max_half_open_probes
        self._clock = clock or time.monotonic

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._half_open_probes = 0
        self._lock = threading.RLock()

    def allow_request(self) -> bool:
        """
        Check if a request is allowed based on the current circuit state.
        
        Returns:
            True if the request should proceed, False if it should be blocked.
            
        Raises:
            CircuitOpenError: If the circuit is OPEN and request should fail fast.
        """
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            elif self.state == CircuitState.OPEN:
                if self._clock() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_probes = 1  # First probe counts
                    return True
                retry_after = self.recovery_timeout - (self._clock() - self.last_failure_time)
                raise CircuitOpenError(self.name, retry_after)

            else:  # HALF_OPEN
                if self._half_open_probes < self.max_half_open_probes:
                    self._half_open_probes += 1
                    return True
                raise CircuitOpenError(self.name, 0.1)

    def record_success(self) -> None:
        """
        Record a successful request. 
        In HALF_OPEN state, a single success closes the circuit.
        In CLOSED state, resets the failure count.
        """
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self._half_open_probes = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self) -> None:
        """
        Record a failed request. 
        May trip the circuit if threshold exceeded in CLOSED state.
        In HALF_OPEN state, immediately re-opens the circuit.
        """
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = self._clock()

            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self._half_open_probes = 0

    def get_state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            # Check for automatic transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._clock() - self.last_failure_time >= self.recovery_timeout:
                    return CircuitState.HALF_OPEN
            return self.state

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0.0
            self._half_open_probes = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CircuitBreaker(state={self.state.value}, "
                f"failures={self.failure_count}, "
                f"threshold={self.failure_threshold}, "
                f"recovery_timeout={self.recovery_timeout}s)"
            )
