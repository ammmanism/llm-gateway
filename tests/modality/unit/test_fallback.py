from unittest.mock import MagicMock

from omnimodal.gateway.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time

        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN


class TestFallbackChain:
    async def test_successful_primary(self, fallback_chain):
        async def success_op(provider):
            return MagicMock(
                content="success", model="gpt-4o", cost=0.01, from_cache=False
            )

        primary = MagicMock(provider="openai", modality="text")
        result = await fallback_chain.execute(primary, success_op)
        assert result.content == "success"
        assert result.fallback_used is False

    async def test_fallback_on_failure(self, fallback_chain):
        call_count = 0

        async def flaky_op(provider):
            nonlocal call_count
            call_count += 1
            if provider == "openai":
                raise Exception("OpenAI down")
            return MagicMock(
                content="fallback", model="claude", cost=0.01, from_cache=False
            )

        primary = MagicMock(provider="openai", modality="text")
        result = await fallback_chain.execute(primary, flaky_op)
        assert result.content == "fallback"
        assert result.fallback_used is True
        assert result.attempts == 2
