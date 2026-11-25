import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uuid

import numpy as np

from src.cache.semantic import SemanticCache


async def run_benchmark():
    cache = SemanticCache()
    # Mocking initialization for benchmark
    cache.dimension = 384
    import faiss

    cache.index = faiss.IndexIDMap(
        faiss.IndexHNSWFlat(384, 32, faiss.METRIC_INNER_PRODUCT)
    )

    # Pre-populate with dummy vectors
    num_vectors = 10000
    print(f"Generating {num_vectors} dummy vectors...")
    dummy_vectors = np.random.rand(num_vectors, 384).astype("float32")
    # L2 normalize
    faiss.normalize_L2(dummy_vectors)
    ids = np.arange(num_vectors)
    cache.index.add_with_ids(dummy_vectors, ids)

    # Create id_map
    for i in range(num_vectors):
        cache.id_map[i] = str(uuid.uuid4())

    print(f"Added {cache.index.ntotal} vectors to FAISS index.")

    # Query performance
    num_queries = 1000
    query_vectors = np.random.rand(num_queries, 384).astype("float32")
    faiss.normalize_L2(query_vectors)

    print(f"Running {num_queries} queries...")
    start = time.time()

    # Sequential search simulating individual requests
    for i in range(num_queries):
        # Search FAISS directly to isolate vector-search cost from Redis.
        cache.index.search(np.array([query_vectors[i]]), k=5)

    end = time.time()
    duration = end - start
    report = {
        "benchmark": "cache_vector_search",
        "vectors": num_vectors,
        "queries": num_queries,
        "total_seconds": round(duration, 4),
        "average_latency_ms": round((duration / num_queries) * 1000, 2),
        "throughput_qps": round(num_queries / duration, 2),
    }
    Path("benchmarks/reports").mkdir(parents=True, exist_ok=True)
    Path("benchmarks/reports/cache.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(run_benchmark())
