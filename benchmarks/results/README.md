# Benchmark Methodology

All benchmarks were run on a **Windows 11** system with **16 GB RAM**, **Intel i7-11800H**, and **Python 3.11**. The results are **falsifiable** - you can run `benchmarks/run_all.py` yourself to reproduce these numbers.

## Cache Benchmarks (`cache_comparison.json`)
- **No Cache**: Each query calls the LLM (simulated with 10ms latency and $0.002 cost).
- **Exact Cache**: Matches queries exactly; only exact duplicates are cached.
- **Semantic Cache**: Uses FAISS with `all-MiniLM-L6-v2` embeddings, threshold = 0.92 cosine similarity.

## Router Benchmarks (`routing_comparison.json`)
- **Round-Robin**: Distributes requests evenly among providers.
- **Cost-Aware**: Selects provider with lowest cost, while respecting latency constraints (weighted multi-objective).

## Failover Recovery (`failover_recovery.json`)
- Simulated provider that fails 5 times in a row.
- Circuit breaker trips after 3 failures, then recovers after 5s timeout.

## Multi-Tenant Isolation (`multi_tenant.json`)
- Three concurrent tenants with different quotas.
- Verified that quota enforcement prevents exceeding limits and no cross-tenant leakage.

## Modality Overhead (`modality_overhead.json`)
- Measures latency added by content-type detection (text, image, video) and routing logic.
- Overhead is minimal (< 2ms on average).

All scripts are in `/benchmarks` and can be executed with `python benchmarks/run_all.py`.
