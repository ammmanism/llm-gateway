"""
Unit tests for Fallback Chain and Circuit Breaker.
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from omnimodal.gateway.fallback import CircuitBreaker, FallbackChain, CircuitState


class TestCircuitBreaker:
    """Test circuit breaker state machine."""
    
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True
    
    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # Not yet
        
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
    
    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout
        import time
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_closes_after_successes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_max_calls=2)
        cb.record_failure()
        cb.state = CircuitState.HALF_OPEN
        
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
    
    def test_reopens_on_half_open_failure(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        cb.state = CircuitState.HALF_OPEN
        
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestFallbackChain:
    """Test fallback chain orchestration."""
    
    @pytest.fixture
    def fallback(self):
        return FallbackChain()
    
    async def test_successful_primary(self, fallback):
        """Should return primary result on success."""
        async def success_op(provider):
            return MagicMock(content="success", model="gpt-4o", cost=0.01, from_cache=False)
        
        primary = MagicMock(provider="openai")
        result = await fallback.execute(primary, success_op)
        
        assert result.content == "success"
        assert result.fallback_used is False
        assert result.attempts == 1
    
    async def test_fallback_on_failure(self, fallback):
        """Should try next provider on failure."""
        call_count = 0
        
        async def flaky_op(provider):
            nonlocal call_count
            call_count += 1
            if provider == "openai":
                raise Exception("OpenAI down")
            return MagicMock(content="fallback", model="claude", cost=0.01, from_cache=False)
        
        primary = MagicMock(provider="openai")
        result = await fallback.execute(primary, flaky_op)
        
        assert result.content == "fallback"
        assert result.fallback_used is True
        assert result.attempts == 2
    
    async def test_all_providers_fail(self, fallback):
        """Should degrade gracefully when all fail."""
        async def always_fail(provider):
            raise Exception("Everything is on fire")
        
        primary = MagicMock(provider="openai")
        result = await fallback.execute(primary, always_fail)
        
        assert "[QUEUED" in result.content or "[DEGRADED" in result.content
        assert result.fallback_used is True
    
    async def test_timeout_handling(self, fallback):
        """Should treat timeouts as failures."""
        async def slow_op(provider):
            await asyncio.sleep(10)
            return MagicMock(content="too late", model="gpt-4o", cost=0.01, from_cache=False)
        
        primary = MagicMock(provider="openai")
        result = await fallback.execute(primary, slow_op, timeout=0.1)
        
        assert result.fallback_used is True
