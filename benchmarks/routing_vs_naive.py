#!/usr/bin/env python3
"""
Compare cost-aware router vs round-robin on latency and total cost.
Uses the real CostAwareRouter from llm_gateway.routing.cost_aware for model
selection, then simulates provider-level latency/cost per selected model.
"""

import asyncio
import json
import random
import time
from pathlib import Path

from llm_gateway.routing.cost_aware import CostAwareRouter

PROVIDER_LATENCY = {
    "gpt-4-turbo": 0.30,
    "claude-3-haiku": 0.15,
    "gpt-3.5-turbo": 0.05,
    "llama-3-8b": 0.02,
}
COST_PER_CALL = {
    "gpt-4-turbo": 0.01,
    "claude-3-haiku": 0.00025,
    "gpt-3.5-turbo": 0.0005,
    "llama-3-8b": 0.0001,
}


async def simulate_request(model):
    """Simulate a call to the given model with realistic latency."""
    latency = PROVIDER_LATENCY.get(model, 0.1)
    jitter = random.uniform(0.8, 1.2)
    await asyncio.sleep(latency * jitter)
    return latency * jitter


async def run_round_robin(models, queries, n=500):
    """Route requests in round-robin order across all available models."""
    latencies = []
    total_cost = 0.0
    for i, q in enumerate(queries[:n]):
        model = models[i % len(models)]
        cost = COST_PER_CALL.get(model, 0.0005)
        total_cost += cost
        start = time.perf_counter()
        await simulate_request(model)
        latencies.append(time.perf_counter() - start)
    if not latencies:
        return {"error": "No requests"}
    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.5)] * 1000
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] * 1000
    return {
        "p50_latency_ms": round(p50, 1),
        "p99_latency_ms": round(p99, 1),
        "total_cost_usd": round(total_cost, 4),
        "n_requests": n,
    }


async def run_cost_aware(router, queries, n=500):
    """Use CostAwareRouter.select_models to pick cheapest model per request."""
    latencies = []
    total_cost = 0.0
    for q in queries[:n]:
        models = await router.select_models(
            {"allowed_models": list(PROVIDER_LATENCY.keys())}
        )
        # Pick the cheapest model returned
        model = models[0]
        cost = router.model_costs.get(model, 0.0005)
        start = time.perf_counter()
        await simulate_request(model)
        latencies.append(time.perf_counter() - start)
        total_cost += cost
    if not latencies:
        return {"error": "No requests"}
    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.5)] * 1000
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] * 1000
    return {
        "p50_latency_ms": round(p50, 1),
        "p99_latency_ms": round(p99, 1),
        "total_cost_usd": round(total_cost, 4),
        "n_requests": n,
    }


async def main():
    queries = ["What is AI?" for _ in range(1000)]
    models = list(PROVIDER_LATENCY.keys())
    router = CostAwareRouter()

    results = {
        "round_robin": await run_round_robin(models, queries, n=500),
        "cost_aware": await run_cost_aware(router, queries, n=500),
    }
    out_file = Path("benchmarks/results/routing_comparison.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
