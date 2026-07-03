"""
Performance benchmarks for latency-critical paths.
"""

import pytest
import asyncio
import time


class TestRouterLatency:
    """Benchmark routing decision latency."""
    
    @pytest.mark.benchmark
    async def test_routing_decision_latency(self, router):
        """Routing decision should be fast."""
        start = time.time()
        result = await router.select(modality="text", quality="standard")
        duration = time.time() - start
        assert result.estimated_latency_ms > 0
        assert duration < 0.05  # Should take less than 50ms (local/mocked)
    
    @pytest.mark.benchmark
    async def test_cache_lookup_latency(self, cost_optimizer):
        """Cache lookup should be fast."""
        start = time.time()
        await cost_optimizer.cache.get("text", "test", {})
        duration = time.time() - start
        assert duration < 0.05
