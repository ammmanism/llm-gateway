# Benchmark evidence

Performance and correctness claims live in `data/evidence/`, not in ignored
JSON files under this directory.

| Evidence | Generator |
|---|---|
| `gateway_overhead_benchmark.csv` | `benchmarks/gateway_overhead.py` |
| `semantic_threshold_sweep.csv` | `benchmarks/semantic_threshold_sweep.py` |
| `fallback_recovery.csv` | `benchmarks/fallback_recovery.py` |
| `cost_ledger_sample.csv` | `benchmarks/cost_attribution_demo.py` |
| `prometheus_metrics_snapshot.txt` | `benchmarks/metrics_snapshot.py` |
| `redis_consistency.csv` | `benchmarks/redis_consistency.py` |
| `budget_atomic_race.csv` | `benchmarks/budget_atomic_race.py` |
| `otel_span_sample.csv` | `benchmarks/otel_span_summary.py` |
| `coverage_summary.csv` | `pytest --cov` + `benchmarks/coverage_summary.py` |

Run all evidence generators with:

```bash
REDIS_URL=redis://localhost:6379/0 OTEL_SDK_DISABLED=true \
  python benchmarks/run_all.py
```

The runner writes an execution-status JSON under `benchmarks/results/` (ignored
by Git) and exits non-zero if any generator fails.
