# Modality benchmarking status

The legacy multi-modal implementation is quarantined under `_superseded/` and
is **not benchmarked by the active gateway**. The previously documented cost,
latency, throughput, cache-hit, and uptime numbers were not backed by committed
raw data and have been removed.

For active, reproducible measurements see:

- `data/evidence/gateway_overhead_benchmark.csv`
- `data/evidence/semantic_threshold_sweep.csv`
- `data/evidence/fallback_recovery.csv`
- `data/evidence/redis_consistency.csv`
- `data/evidence/coverage_summary.csv`

The generators and methodology are indexed in `benchmarks/results/README.md`.
