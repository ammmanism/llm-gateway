# Gap analysis

This is the honest scorecard for the five-phase overhaul. "Done" means the
artifact exists **and** its evidence file is committed. A missing screenshot or
an unrun integration is listed here rather than papered over.

_Last updated: 2026-11-25._

## Phase status

| Phase | Goal | Status | Evidence |
|---|---|---|---|
| 1 | Resilience, dual-metric limits, observability | ✅ Done | `fallback_recovery.csv`, `fallback_timeline_events.csv`, `fallback_trigger_matrix.csv`, `prometheus_metrics_snapshot.txt`, `deploy/grafana/llm_gateway_dashboard.json`, `docs/evidence/figures/grafana_dashboard.png` |
| 2 | Exact + semantic cache, cost ledger | ✅ Done | `cost_ledger_sample.csv`, `semantic_threshold_sweep.csv`, `tests/billing`, `tests/cache/test_two_tier_cache.py` |
| 3 | Reproducible performance evidence | ✅ Done | `gateway_overhead_benchmark.csv`, `semantic_threshold_sweep.csv`, `fallback_recovery.csv`, four PNG figures |
| 4 | README + competitive analysis | ✅ Done | `README.md`, `docs/COMPETITIVE_ANALYSIS.md`, `docs/evidence/figures/*.png` |
| 5 | Gap analysis + lessons + audit | ✅ Done | this file, `docs/LESSONS.md` |

## Evidence inventory

Every number quoted in the README comes from one of these files. The script in
the third column regenerates it.

| Evidence file | What it proves | Generator |
|---|---|---|
| `data/evidence/gateway_overhead_benchmark.csv` | In-process gateway adds **10.5 ms p50 / 22.4 ms p95 / 33.7 ms p99** over a direct provider coroutine; concurrent throughput at 8 workers | `benchmarks/gateway_overhead.py` |
| `data/evidence/semantic_threshold_sweep.csv` | Threshold trade-off on 24 paraphrases + 24 negatives; `0.85` is the chosen default | `benchmarks/semantic_threshold_sweep.py` |
| `data/evidence/fallback_recovery.csv` | Detection ~101–205 ms, recovery 0.5–5 s across five breaker scenarios | `benchmarks/fallback_recovery.py` |
| `data/evidence/fallback_timeline_events.csv` | Per-event circuit states and provider names for the timeline figure | `benchmarks/fallback_recovery.py` |
| `data/evidence/fallback_trigger_matrix.csv` | Which errors trigger fallback vs. stop the chain | `benchmarks/` fallback matrix script |
| `data/evidence/cost_ledger_sample.csv` | Four provider rows + one cache-hit row at $0 from the real SQLite ledger | `benchmarks/cost_attribution_demo.py` |
| `data/evidence/prometheus_metrics_snapshot.txt` | Real `/metrics` exposition with requests, cache hits/misses, cost, tokens | `benchmarks/metrics_snapshot.py` |
| `docs/evidence/figures/grafana_dashboard.png` | Live Grafana dashboard populated by the running gateway (request rate, cache ratio, latency, cost, fallbacks, rate limits) | `deploy/observability/docker-compose.yml` + `benchmarks/capture_grafana.py` |
| `data/evidence/otel_span_sample.csv` | Real OTLP collector export with provider/model/token/cost/latency/cache attributes | `deploy/observability/otel-collector-config.yaml` + `benchmarks/otel_span_summary.py` |
| `data/evidence/redis_consistency.csv` | Two workers share RPM limits and exact cache; concurrent budget increments sum exactly | `benchmarks/redis_consistency.py` |
| `data/evidence/budget_atomic_race.csv` | 200 concurrent reservations never exceed a $1 cap; zero overspend | `benchmarks/budget_atomic_race.py` |
| `data/evidence/coverage_summary.csv` | Real statement/branch coverage by module | `pytest --cov` + `benchmarks/coverage_summary.py` |
| `data/evidence/streaming_accounting.csv` | Sync/stream token and cost parity across 20 request pairs | `benchmarks/streaming_accounting.py` |
| `docs/evidence/figures/gateway_overhead.png` | Chart of the overhead CSV | `benchmarks/plot_evidence.py` |
| `docs/evidence/figures/semantic_threshold_tradeoff.png` | Chart of the sweep CSV | `benchmarks/plot_evidence.py` |
| `docs/evidence/figures/fallback_recovery_timeline.png` | Chart of the timeline CSV | `benchmarks/plot_evidence.py` |

## Open gaps

### Medium priority

1. **Branch coverage is 57.13%.** The report is real and committed, and CI
   publishes HTML/XML artifacts, but coverage is below a production-oriented
   target. Next step: add provider-adapter and fallback-policy edge-case tests.
2. **Semantic cache is per process.** The FAISS index is in-process. Production
   multi-replica deployments need a shared vector store or an external cache.
3. **Redis evidence is correctness, not scale.** A two-worker check proves shared
   RPM/TPM state, exact-cache visibility, and budget aggregation. It is not a
   high-concurrency load test.

### Low priority / non-goals

4. **No managed UI.** There is no Next.js control plane in the evidence path.
5. **No MCP gateway, no guardrail catalogue.** Out of scope; see
   `docs/COMPETITIVE_ANALYSIS.md`.
6. **Benchmarks use a deterministic fake provider.** This isolates gateway
   overhead from provider network variance. It is not a claim about real
   provider latency or spend.

## Closed during the quality pass

- Repo-wide Ruff lint and formatting are green.
- Coverage is measured with branch data and published by CI.
- OTLP export was verified through a real OpenTelemetry Collector.
- Redis paths were verified with two independent worker processes.
- Provider usage normalization is covered for OpenAI/Anthropic/Gemini/Together,
  Groq, Ollama, and vLLM response shapes.
- Budget reservation is atomic in Redis and memory, wired per provider attempt,
  and verified with zero overshoot under 200 concurrent reservations.
- Virtual keys now support hashed storage, scopes, expiry, revocation, rotation,
  per-key RPM/TPM/budgets, SQLite/Postgres backends, Redis caching, and admin
  scope enforcement.
- OpenAI-compatible chat completions support the official SDK for non-streaming
  and SSE streaming; both paths record tokens, cost, ledger rows, and cleanup.
- CI runs the full test suite and the real evidence generators instead of stale
  benchmark JSON.

## Test and lint status (actual)

```
python -m pytest tests/ -q
130 passed, 8 warnings in 52.10s (0:00:52)
```

```
python -m ruff check .
All checks passed!

python -m ruff format --check .
150 files already formatted
```

Branch coverage: **57.13%** (`data/evidence/coverage_summary.csv`).

`tests/modality` was quarantined to `_superseded/tests-modality/` with a README
explaining that it targets removed `SemanticRouter` / `CostOptimizer` /
`FallbackChain` APIs. It is not silently deleted.
