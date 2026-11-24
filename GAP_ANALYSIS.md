# Gap analysis

This is the honest scorecard for the five-phase overhaul. "Done" means the
artifact exists **and** its evidence file is committed. A missing screenshot or
an unrun integration is listed here rather than papered over.

_Last updated: 2026-11-24._

## Phase status

| Phase | Goal | Status | Evidence |
|---|---|---|---|
| 1 | Resilience, dual-metric limits, observability | ✅ Done | `fallback_recovery.csv`, `fallback_timeline_events.csv`, `fallback_trigger_matrix.csv`, `prometheus_metrics_snapshot.txt`, `deploy/grafana/llm_gateway_dashboard.json`, `docs/evidence/figures/grafana_dashboard.png` |
| 2 | Exact + semantic cache, cost ledger | ✅ Done | `cost_ledger_sample.csv`, `semantic_threshold_sweep.csv`, `tests/billing`, `tests/cache/test_two_tier_cache.py` |
| 3 | Reproducible performance evidence | ✅ Done | `gateway_overhead_benchmark.csv`, `semantic_threshold_sweep.csv`, `fallback_recovery.csv`, three PNG figures |
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
| `docs/evidence/figures/gateway_overhead.png` | Chart of the overhead CSV | `benchmarks/plot_evidence.py` |
| `docs/evidence/figures/semantic_threshold_tradeoff.png` | Chart of the sweep CSV | `benchmarks/plot_evidence.py` |
| `docs/evidence/figures/fallback_recovery_timeline.png` | Chart of the timeline CSV | `benchmarks/plot_evidence.py` |

## Open gaps

### High priority

1. **Trace export is unverified end-to-end.** Spans are created and attributes
   are set, and `OTEL_EXPORTER_OTLP_ENDPOINT` is honoured, but tests log
   `UNAVAILABLE: localhost:4317` because no collector is running. The span
   plumbing is covered by code and tests; the export path is not.
2. **Repo-wide lint is red.** `python -m ruff check .` fails on pre-existing
   line-length (`E501`) and whitespace (`W291`/`W293`) debt, especially
   `core/server.py`. New Phase 2/3 files pass a focused `ruff` check. Next step:
   format the legacy files in an isolated commit.
3. **Coverage is not measured.** The old README claimed 42%; that number is
   removed. Next step: add `pytest-cov` and commit a real report.

### Medium priority

4. **Redis paths are not load-tested.** Rate limiting, budgets, and the exact
   cache all have in-memory fallbacks that the evidence runs use. The Redis/Lua
   paths exist and are unit-tested where practical, but there is no multi-worker
   evidence.
5. **Semantic cache is per process.** The FAISS index is in-process. Production
   multi-replica deployments need a shared vector store or an external cache.
6. **Provider usage passthrough is uneven.** OpenAI, Anthropic, Gemini, and
   Together propagate usage; other adapters fall back to the explicit
   `usage_source="estimated"` path. This is labelled, not hidden.
7. **Auth is a demonstration.** `APIKeyAuthMiddleware` validates an `sk-` prefix
   and maps keys to tenants via `TENANT_API_KEYS`. It is not a virtual-key
   database with rotation and scopes.

### Low priority / non-goals

8. **No managed UI.** There is no Next.js control plane in the evidence path.
9. **No MCP gateway, no guardrail catalogue.** Out of scope; see
   `docs/COMPETITIVE_ANALYSIS.md`.
10. **Benchmarks use a deterministic fake provider.** This isolates gateway
    overhead from provider network variance. It is not a claim about real
    provider latency or spend.

## Test and lint status (actual)

```
python -m pytest tests/ -q
69 passed, 11 warnings
```

```
python -m ruff check .        # expected red (pre-existing debt)
```

`tests/modality` was quarantined to `_superseded/tests-modality/` with a README
explaining that it targets removed `SemanticRouter` / `CostOptimizer` /
`FallbackChain` APIs. It is not silently deleted.
