"""Measure exact-cache hit rate on a deterministic repeated workload."""

import asyncio
import json
import time

from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.utils.embeddings import HashingEmbedder


async def run_benchmark() -> dict:
    cache = TwoTierCache(
        exact_cache=CacheManager(),
        semantic_index=SemanticIndex(embedder=HashingEmbedder()),
        threshold=0.85,
    )
    prompts = [f"deterministic cache benchmark prompt {i}" for i in range(100)]
    workload = prompts * 10

    start = time.perf_counter()
    hits = 0
    for prompt in workload:
        result = await cache.get(
            prompt,
            tenant_id="benchmark",
            model="fake",
            params={"temperature": 0.0, "max_tokens": 16},
        )
        if result is not None:
            hits += 1
        else:
            await cache.set(
                prompt,
                {"output": "ok", "provider": "fake", "model": "fake"},
                tenant_id="benchmark",
                model="fake",
                params={"temperature": 0.0, "max_tokens": 16},
            )
    elapsed = time.perf_counter() - start

    return {
        "benchmark": "cache_hit_rate",
        "queries": len(workload),
        "unique_prompts": len(prompts),
        "cache_hits": hits,
        "hit_rate": round(hits / len(workload), 4),
        "elapsed_seconds": round(elapsed, 6),
        "backend": "exact-memory",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_benchmark()), indent=2))
