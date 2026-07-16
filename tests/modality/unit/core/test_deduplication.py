import asyncio

from omnimodal.core.deduplication import RequestCoalescer


class TestRequestCoalescer:
    async def test_exact_dedup(self):
        coalescer = RequestCoalescer(exact_ttl_seconds=5.0)
        call_count = 0

        async def exec_fn():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return "result"

        results = await asyncio.gather(
            *[
                coalescer.execute_or_wait("text", "hello world", {}, exec_fn)
                for _ in range(10)
            ]
        )

        assert call_count == 1
        assert all(r == "result" for r in results)
        assert coalescer.coalesced_count == 9

    async def test_different_params_no_dedup(self):
        coalescer = RequestCoalescer(exact_ttl_seconds=5.0)
        call_count = 0

        async def exec_fn():
            nonlocal call_count
            call_count += 1
            return "result"

        await coalescer.execute_or_wait("text", "prompt a", {}, exec_fn)
        await coalescer.execute_or_wait("text", "prompt b", {}, exec_fn)

        assert call_count == 2
        assert coalescer.coalesced_count == 0

    async def test_ttl_cleanup(self):
        coalescer = RequestCoalescer(exact_ttl_seconds=0.1)
        call_count = 0

        async def exec_fn():
            nonlocal call_count
            call_count += 1
            return "result"

        await coalescer.execute_or_wait("text", "prompt", {}, exec_fn)
        await asyncio.sleep(0.2)
        assert len(coalescer.exact_inflight) == 0

    async def test_batching(self):
        coalescer = RequestCoalescer(max_batch_size=3)

        async def batch_exec(requests):
            return [f"processed {r}" for r in requests]

        tasks = [
            coalescer.execute_batched(
                "test_batch", {"id": i}, batch_exec, max_wait_ms=200
            )
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

        assert coalescer.batched_count >= 5

    async def test_semantic_dedup(self):
        coalescer = RequestCoalescer(semantic_ttl_seconds=5.0, exact_ttl_seconds=0.1)
        call_count = 0

        async def exec_fn():
            nonlocal call_count
            call_count += 1
            return "result"

        await coalescer.execute_or_wait(
            "text", "What is the weather", {}, exec_fn, use_semantic=True
        )
        await coalescer.execute_or_wait(
            "text", "What is the weather outside", {}, exec_fn, use_semantic=True
        )

        assert call_count == 2

    def test_get_stats(self):
        coalescer = RequestCoalescer()
        stats = coalescer.get_stats()
        assert "coalesced_requests" in stats
        assert "batched_requests" in stats
        assert stats["coalesced_requests"] == 0
