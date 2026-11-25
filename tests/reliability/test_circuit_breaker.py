import threading
import time

import pytest

from llm_gateway.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreakerBasics:
    """Test basic circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        assert cb.get_state() == CircuitState.CLOSED

    def test_allow_request_in_closed_state(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        assert cb.allow_request() is True

    def test_failure_count_increments_on_record_failure(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

    def test_success_resets_failure_count_in_closed_state(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0

    def test_transitions_to_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()  # 3rd failure - should trip
        assert cb.get_state() == CircuitState.OPEN

    def test_open_state_blocks_requests(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()  # Now OPEN
        with pytest.raises(CircuitOpenError):
            cb.allow_request()


class TestCircuitBreakerHalfOpen:
    """Test HALF_OPEN state transitions."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()  # OPEN
        time.sleep(0.15)  # Wait for recovery timeout
        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_probes(self):
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, max_half_open_probes=2
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        # First probe allowed
        assert cb.allow_request() is True
        # Second probe allowed
        assert cb.allow_request() is True
        # Third probe should be rejected
        with pytest.raises(CircuitOpenError):
            cb.allow_request()

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        cb.allow_request()  # Enter HALF_OPEN
        cb.record_success()  # Probe succeeds

        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        cb.allow_request()  # Enter HALF_OPEN
        cb.record_failure()  # Probe fails

        assert cb.get_state() == CircuitState.OPEN

    def test_half_open_probe_counter_resets_on_close(self):
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, max_half_open_probes=1
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        cb.allow_request()  # Probe 1
        cb.record_success()  # Success -> CLOSED

        # Trip again
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        # Should allow probe again (counter reset)
        assert cb.allow_request() is True


class TestCircuitBreakerConcurrency:
    """Test thread-safety of circuit breaker."""

    def test_concurrent_access_thread_safe(self):
        cb = CircuitBreaker(failure_threshold=100, recovery_timeout=1.0)
        errors = []

        def worker():
            try:
                for _ in range(100):
                    cb.allow_request()
                    cb.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.get_state() == CircuitState.CLOSED

    def test_concurrent_failure_recording(self):
        cb = CircuitBreaker(failure_threshold=50, recovery_timeout=1.0)
        errors = []

        def worker():
            try:
                for _ in range(10):
                    cb.allow_request()
                    cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.failure_count == 50
        assert cb.get_state() == CircuitState.OPEN


class TestCircuitBreakerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

        cb.reset()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_open_error_contains_retry_after(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5.0)
        cb.record_failure()  # OPEN

        with pytest.raises(CircuitOpenError) as exc_info:
            cb.allow_request()

        assert exc_info.value.retry_after > 0
        assert exc_info.value.retry_after <= 5.0

    def test_custom_clock_for_testing(self):
        clock_time = [0.0]

        def mock_clock():
            return clock_time[0]

        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=10.0, clock=mock_clock
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

        # Advance clock past recovery timeout
        clock_time[0] = 15.0
        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_repr_includes_state_info(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        repr_str = repr(cb)
        assert "CLOSED" in repr_str
        assert "failures=0" in repr_str
        assert "threshold=3" in repr_str
        assert "recovery_timeout=30.0" in repr_str


class TestCircuitBreakerIntegration:
    """Test realistic usage patterns."""

    def test_full_lifecycle_closed_open_half_open_closed(self):
        """Test complete lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Normal operation
        assert cb.allow_request() is True
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

        # Failures trip the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

        # Requests fail fast
        with pytest.raises(CircuitOpenError):
            cb.allow_request()

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.get_state() == CircuitState.HALF_OPEN

        # Probe succeeds
        cb.allow_request()
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

    def test_full_lifecycle_closed_open_half_open_open(self):
        """Test lifecycle where probe fails: CLOSED -> OPEN -> HALF_OPEN -> OPEN"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.get_state() == CircuitState.HALF_OPEN

        # Probe fails
        cb.allow_request()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

    def test_rapid_failure_recovery_cycles(self):
        """Test multiple failure/recovery cycles."""
        # Use mock clock for deterministic timing
        clock_time = [0.0]

        def mock_clock():
            return clock_time[0]

        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.05, clock=mock_clock
        )

        for i in range(3):
            # Trip
            cb.record_failure()
            cb.record_failure()
            assert cb.get_state() == CircuitState.OPEN

            # Advance clock past recovery timeout
            clock_time[0] += 0.06
            cb.allow_request()
            cb.record_success()
            assert cb.get_state() == CircuitState.CLOSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
