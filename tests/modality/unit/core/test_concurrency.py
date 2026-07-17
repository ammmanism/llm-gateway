import asyncio

from llm_gateway.core.concurrency import AdaptiveConcurrencyLimiter


class TestAdaptiveConcurrencyLimiter:
    async def test_acquire_release(self):
        limiter = AdaptiveConcurrencyLimiter()
        acquired = await limiter.acquire("openai")
        assert acquired is True
        limiter.release("openai", success=True, latency_ms=100)
        await asyncio.sleep(0.05)

        window = limiter._get_window("openai")
        assert window.in_flight == 0

    async def test_limit_enforced(self):
        limiter = AdaptiveConcurrencyLimiter()
        window = limiter._get_window("openai")
        window.current_limit = 2

        acquired1 = await limiter.acquire("openai")
        acquired2 = await limiter.acquire("openai")
        acquired3 = await limiter.acquire("openai")

        assert acquired1 is True
        assert acquired2 is True
        assert acquired3 is False

    async def test_aimd_increase_on_success(self):
        limiter = AdaptiveConcurrencyLimiter()
        provider = "openai"

        for _ in range(100):
            await limiter.acquire(provider)
            limiter.release(provider, success=True, latency_ms=100)

        await asyncio.sleep(0.1)
        window = limiter._get_window(provider)
        assert window.current_limit > 10

    async def test_aimd_decrease_on_failure(self):
        limiter = AdaptiveConcurrencyLimiter()
        provider = "openai"
        window = limiter._get_window(provider)
        window.current_limit = 100

        for _ in range(10):
            await limiter.acquire(provider)
            limiter.release(provider, success=False, latency_ms=100)

        await asyncio.sleep(0.1)
        assert window.current_limit < 100

    async def test_wait_and_acquire(self):
        limiter = AdaptiveConcurrencyLimiter()
        window = limiter._get_window("openai")
        window.current_limit = 0

        acquired = await limiter.wait_and_acquire("openai", max_wait_seconds=0.1)
        assert acquired is False

    async def test_rate_limit_backoff(self):
        limiter = AdaptiveConcurrencyLimiter()
        window = limiter._get_window("openai")
        window.current_limit = 100

        limiter.handle_rate_limit("openai", retry_after=0.05)
        await asyncio.sleep(0.1)

        assert window.current_limit >= 1

    async def test_get_stats(self):
        limiter = AdaptiveConcurrencyLimiter()
        await limiter.acquire("openai")
        limiter.release("openai", success=True, latency_ms=50)
        await asyncio.sleep(0.05)

        stats = limiter.get_stats()
        assert "openai" in stats
        assert stats["openai"]["success_rate"] >= 0
