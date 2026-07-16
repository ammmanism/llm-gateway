"""
Circuit Breaker Pattern
"""

import logging
import time
from enum import Enum, auto

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    """
    Prevents cascade failures by failing fast when a provider is unhealthy.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: float = 0.0
        self.successes = 0
        self.total_calls = 0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.total_calls < self.half_open_max_calls

        return False

    def record_success(self):
        self.failures = 0
        self.total_calls += 1

        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.total_calls = 0
                logger.info("Circuit closed after successful half-open")

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        self.total_calls += 1

        if (
            self.state == CircuitState.CLOSED
            and self.failures >= self.failure_threshold
        ):
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit opened after {self.failures} failures")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit reopened after failure in half-open")
