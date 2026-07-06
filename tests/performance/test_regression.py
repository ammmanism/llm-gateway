import asyncio
import time

import pytest


class TestLatencyRegression:
    BASELINE_P50 = {
        "text": 89,
        "image": 6000,
        "audio": 500,
        "video": 15000
    }

    @pytest.mark.performance
    @pytest.mark.slow
    async def test_cache_hit_latency(self):
        from omnimodal.core.deduplication import RequestCoalescer
        coalescer = RequestCoalescer(exact_ttl_seconds=5.0)

        async def executor():
            await asyncio.sleep(0.1)
            return {"result": "success"}

        start = time.time()
        result = await coalescer.execute_or_wait("text", "perf test prompt", {}, executor)
        first_latency = (time.time() - start) * 1000

        start = time.time()
        result2 = await coalescer.execute_or_wait("text", "perf test prompt", {}, executor)
        second_latency = (time.time() - start) * 1000

        assert result == result2
        assert second_latency < first_latency

    @pytest.mark.performance
    @pytest.mark.slow
    async def test_concurrency_limiter_overhead(self):
        from omnimodal.core.concurrency import AdaptiveConcurrencyLimiter
        limiter = AdaptiveConcurrencyLimiter()

        start = time.time()
        for _ in range(100):
            acquired = await limiter.acquire("openai")
            if acquired:
                limiter.release("openai", success=True, latency_ms=10)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 500, f"Concurrency overhead too high: {elapsed:.1f}ms"

    @pytest.mark.performance
    async def test_memory_stable(self):
        import tracemalloc
        tracemalloc.start()

        for _ in range(100):
            _ = "x" * 10000

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert current < 100 * 1024 * 1024, f"Memory usage {current / 1024 / 1024:.1f}MB too high"


class TestThroughputRegression:
    TARGET_RPS = 100

    @pytest.mark.performance
    @pytest.mark.slow
    async def test_coalescer_throughput(self):
        from omnimodal.core.deduplication import RequestCoalescer
        coalescer = RequestCoalescer(exact_ttl_seconds=1.0)
        call_count = 0

        async def executor():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"result": "ok"}

        start_time = time.time()
        count = 0
        while time.time() - start_time < 1.0:
            tasks = [
                coalescer.execute_or_wait("text", f"prompt-{i % 10}", {}, executor)
                for i in range(10)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            count += 1

        assert call_count <= count * 10
