#!/usr/bin/env python3
"""
Benchmark exact and semantic cache hit rates and cost savings.
Uses mock LLM compute with a fixed cost per query.
"""
import json
import random
import time
from pathlib import Path

QUERY_FILE = Path("benchmarks/data/queries.json")
NUM_QUERIES = 1000
COST_PER_CALL = 0.002

def load_queries():
    if QUERY_FILE.exists():
        with open(QUERY_FILE) as f:
            return json.load(f)
    base = [
        "What is the capital of France?",
        "Explain quantum computing in simple terms.",
        "How to fix a leaking faucet?",
        "Write a Python function to sort a list.",
        "Summarize the plot of The Great Gatsby.",
    ]
    queries = []
    for _ in range(200):
        q = random.choice(base)
        if random.random() < 0.3:
            q = q.replace("?", "? Please") if random.random() > 0.5 else q + " - I need help"
        queries.append(q)
    for i in range(800):
        queries.append(f"Unique query #{i}: What is the weather today?")
    return queries[:NUM_QUERIES]

def compute_fn(query):
    time.sleep(0.01)
    return {"response": f"Response to {query}"}

class NoCache:
    def get_or_compute(self, query, compute_fn):
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()

class ExactCache:
    def __init__(self):
        self.cache = {}
    def get_or_compute(self, query, compute_fn):
        if query in self.cache:
            return type('', (), {'was_cached': True, 'estimated_cost': 0})()
        self.cache[query] = compute_fn(query)
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()

class SemanticCache:
    def __init__(self, threshold=0.92):
        self.cache = {}
        self.threshold = threshold
    def get_or_compute(self, query, compute_fn):
        for cached_query in self.cache:
            similarity = self._cosine_similarity(query, cached_query)
            if similarity >= self.threshold:
                return type('', (), {'was_cached': True, 'estimated_cost': 0})()
        self.cache[query] = compute_fn(query)
        return type('', (), {'was_cached': False, 'estimated_cost': 0})()
    def _cosine_similarity(self, a, b):
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        return len(intersection) / (len(set_a)**0.5 * len(set_b)**0.5)

def run_benchmark(queries, cache):
    hits = 0
    cost_saved = 0.0
    start = time.perf_counter()
    for q in queries:
        result = cache.get_or_compute(q, compute_fn=compute_fn)
        if result.was_cached:
            hits += 1
            cost_saved += COST_PER_CALL
    elapsed = time.perf_counter() - start
    return {
        "hit_rate": round(hits / len(queries), 4),
        "cost_saved_usd": round(cost_saved, 4),
        "queries": len(queries),
        "elapsed_seconds": round(elapsed, 2),
    }

if __name__ == "__main__":
    queries = load_queries()
    results = {
        "no_cache": run_benchmark(queries, NoCache()),
        "exact_cache": run_benchmark(queries, ExactCache()),
        "semantic_cache": run_benchmark(queries, SemanticCache(threshold=0.92)),
    }
    out_file = Path("benchmarks/results/cache_comparison.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
