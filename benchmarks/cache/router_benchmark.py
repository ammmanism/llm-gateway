"""Measure in-memory adaptive-router decision throughput."""

import asyncio
import json
import time
from pathlib import Path

from llm_gateway.routing.adaptive import AdaptiveRouter

MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3-haiku-20240307"]


async def run_benchmark() -> None:
    router = AdaptiveRouter()
    router.redis_url = None
    for model in MODELS:
        await router.record_result(model, True, latency_ms=100.0)

    routes = 10_000
    start = time.perf_counter()
    for _ in range(routes):
        await router.select_models({})
    duration = time.perf_counter() - start

    report = {
        "benchmark": "adaptive_router",
        "routes": routes,
        "total_seconds": round(duration, 4),
        "average_latency_ms": round(duration / routes * 1000, 4),
        "throughput_routes_per_sec": round(routes / duration, 2),
        "backend": "in-memory",
    }
    output = Path("benchmarks/reports/router.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(run_benchmark())
