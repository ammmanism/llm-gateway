#!/usr/bin/env python3
"""
Compare cost-aware router vs round-robin on latency and total cost.
Uses mock providers with configurable costs and latencies.
"""
import json
import random
import time
from pathlib import Path

PROVIDER_COSTS = {
    "openai": 0.002,
    "anthropic": 0.003,
    "groq": 0.001,
    "gemini": 0.0015,
}
PROVIDER_LATENCY = {
    "openai": 0.03,
    "anthropic": 0.04,
    "groq": 0.015,
    "gemini": 0.025,
}

class MockProvider:
    def __init__(self, name):
        self.name = name
        self.cost = PROVIDER_COSTS[name]
        self.latency = PROVIDER_LATENCY[name]
    def generate(self, query):
        time.sleep(random.uniform(self.latency * 0.8, self.latency * 1.2))
        return {
            "content": f"Response from {self.name}",
            "cost": self.cost,
            "latency": self.latency,
        }

class RoundRobinRouter:
    def __init__(self, providers):
        self.providers = providers
        self.counter = 0
    def route(self, query):
        provider = self.providers[self.counter % len(self.providers)]
        self.counter += 1
        result = provider.generate(query)
        return type('', (), {'content': result['content'], 'cost': result['cost'], 'latency': result['latency']})()

class CostAwareRouter:
    def __init__(self, providers, cost_weight=0.7, latency_weight=0.3):
        self.providers = providers
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight
    def route(self, query):
        max_cost = max(p.cost for p in self.providers) or 1
        max_latency = max(p.latency for p in self.providers) or 1
        best_provider = None
        best_score = float('inf')
        for provider in self.providers:
            norm_cost = provider.cost / max_cost
            norm_latency = provider.latency / max_latency
            score = self.cost_weight * norm_cost + self.latency_weight * norm_latency
            if score < best_score:
                best_score = score
                best_provider = provider
        result = best_provider.generate(query)
        return type('', (), {'content': result['content'], 'cost': result['cost'], 'latency': result['latency']})()

def run_benchmark(router, queries, n=500):
    latencies = []
    total_cost = 0.0
    errors = 0
    for q in queries[:n]:
        try:
            start = time.perf_counter()
            result = router.route(q)
            latencies.append(time.perf_counter() - start)
            total_cost += result.cost
        except Exception:
            errors += 1
    if len(latencies) == 0:
        return {"error": "No successful requests"}
    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat)*0.5)] * 1000
    p99 = sorted_lat[int(len(sorted_lat)*0.99)] * 1000
    return {
        "p50_latency_ms": round(p50, 1),
        "p99_latency_ms": round(p99, 1),
        "total_cost_usd": round(total_cost, 4),
        "error_rate": errors / n,
        "n_requests": n,
    }

def load_queries():
    qfile = Path("benchmarks/data/queries.json")
    if qfile.exists():
        import json
        with open(qfile) as f:
            return json.load(f)
    return ["What is AI?" for _ in range(1000)]

if __name__ == "__main__":
    queries = load_queries()
    providers = [MockProvider(name) for name in PROVIDER_COSTS.keys()]
    routers = {
        "round_robin": RoundRobinRouter(providers),
        "cost_aware": CostAwareRouter(providers, cost_weight=0.7, latency_weight=0.3),
    }
    results = {name: run_benchmark(router, queries) for name, router in routers.items()}
    out_file = Path("benchmarks/results/routing_comparison.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
