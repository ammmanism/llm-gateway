<h1 align="center">llm-gateway</h1>

<p align="center"><strong>A small, test-backed LLM gateway where every number is reproducible.</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/tests-116%20passing-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <img src="docs/evidence/figures/gateway_overhead.png" width="760" alt="Gateway processing overhead: p50 10.5 ms, p95 22.4 ms, p99 33.7 ms over 500 paired samples">
</p>

<p align="center"><em>Measured, not aspirational: 500 interleaved samples, gateway minus direct provider coroutine. Source: <a href="data/evidence/gateway_overhead_benchmark.csv"><code>gateway_overhead_benchmark.csv</code></a>.</em></p>

---

## What this is

A compact Python/FastAPI reference implementation of the core parts of an AI
gateway: dual-metric rate limiting, a real three-state circuit breaker,
data-driven fallback, a two-tier exact + semantic cache, per-attempt cost
attribution, and OpenTelemetry / Prometheus instrumentation.

It is built to be **read and reproduced**, not to out-scale LiteLLM, Portkey, or
Bifrost. See [`docs/COMPETITIVE_ANALYSIS.md`](docs/COMPETITIVE_ANALYSIS.md) for an
honest feature comparison, and [`GAP_ANALYSIS.md`](GAP_ANALYSIS.md) for what is
still missing.

## Problem → solution → evidence

| Problem | What this repo does | Evidence |
|---|---|---|
| Gateways add latency you cannot see | Interleaved paired benchmark against the raw provider coroutine, both in one event loop | **10.5 ms p50** overhead · [CSV](data/evidence/gateway_overhead_benchmark.csv) · [chart](docs/evidence/figures/gateway_overhead.png) |
| Semantic caches silently return the wrong answer | Two-tier cache (exact SHA-256 → FAISS HNSW) with a threshold swept against **hard negatives** | `0.85` → **29.2%** paraphrase hits, **0** hard-negative false positives · [CSV](data/evidence/semantic_threshold_sweep.csv) · [chart](docs/evidence/figures/semantic_threshold_tradeoff.png) |
| One provider outage takes the product down | CLOSED/OPEN/HALF_OPEN breaker with capped probes and a YAML fallback chain | Detect **~101 ms**, recover **~2 s** (2 s timeout scenario) · [CSV](data/evidence/fallback_recovery.csv) · [timeline](docs/evidence/figures/fallback_recovery_timeline.png) |
| You cannot say who spent what | SQLite ledger, one row per `(request_id, attempt)`, cache hits recorded at $0 | 4 provider rows + 1 cache hit · [CSV](data/evidence/cost_ledger_sample.csv) · [`/v1/costs`](src/llm_gateway/core/server.py) |
| Metrics exist but nothing populates them | Prometheus counters/histograms on the real request path | [Exposition snapshot](data/evidence/prometheus_metrics_snapshot.txt) · [Grafana dashboard JSON](deploy/grafana/llm_gateway_dashboard.json) · [screenshot](docs/evidence/figures/grafana_dashboard.png) |
| Distributed state is hard to trust | Two independent workers share RPM limits, exact cache, and budget totals through Redis | 10/20 requests allowed, cache shared, `$2.00` summed exactly · [CSV](data/evidence/redis_consistency.csv) |
| Concurrent requests can overspend a hard cap | Atomic per-attempt budget reservation with reconcile/release | 200 reservations → 100 allowed, **$0.000000 overspend** · [CSV](data/evidence/budget_atomic_race.csv) |
| Traces may be created but never exported | Real OTLP collector captures the `generate_request` span and all required attributes | [Span CSV](data/evidence/otel_span_sample.csv) · [collector config](deploy/observability/otel-collector-config.yaml) |

## Measured results

All values are copied from committed CSVs. The scripts are in `benchmarks/`.

| Benchmark | Result |
|---|---|
| Gateway overhead, sequential (500 paired samples) | p50 **10.5 ms**, p95 **22.4 ms**, p99 **33.7 ms** |
| Gateway throughput, 8 concurrent (200 requests) | p50 **60.7 ms**, **114.7 req/s** on a Windows dev box |
| Semantic cache, threshold `0.85` | **29.2%** paraphrase hit rate, **0%** hard-negative FP, **0%** unrelated FP |
| Semantic cache, threshold `0.80` | **37.5%** hit rate, **8.3%** hard-negative FP (one wrong answer) |
| Semantic cache, threshold `0.95` (old default) | **0%** hit rate on the same 24 paraphrases |
| Circuit breaker, 2 s recovery timeout | detect **101 ms**, recover **2049 ms**, all 5 scenarios recovered |
| Test suite | **116 passed** with Redis + Postgres enabled (`python -m pytest tests/ -q`) |
| Branch coverage | **53.84%** — 2,254 / 3,910 statements, 339 / 906 branches · [CSV](data/evidence/coverage_summary.csv) |
| Redis consistency | 2 workers: **10/20** RPM attempts allowed, cache shared, budget total exact |
| Atomic budget race | 200 reservations → **100 allowed**, **$0.000000 overspend** |
| OTLP export | real collector captured `provider`, `model`, tokens, cost, latency, cache flag |

The overhead is dominated by auth, validation, dual-metric rate limiting,
routing, token accounting, eight metric updates, and the cost-ledger enqueue.
It is under 2% of a typical 1-second provider call.

### Live dashboard

![Grafana dashboard populated by the running gateway](docs/evidence/figures/grafana_dashboard.png)

The screenshot is from a live run: the gateway served 94 successful requests and
36 rate-limited requests, Prometheus scraped `/metrics`, and Grafana rendered
the provisioned dashboard (`deploy/observability/docker-compose.yml`). Every
panel queries a metric that the request path actually updates.

## Features

| Feature | Implementation | Proof |
|---|---|---|
| **Dual-metric rate limiting** | RPM + TPM per tenant, Redis Lua sliding window with an in-memory fallback | [`security/rate_limiter.py`](src/llm_gateway/security/rate_limiter.py) · [design](docs/evidence/architecture/rate_limiting_design.md) |
| **Three-state circuit breaker** | CLOSED/OPEN/HALF_OPEN, capped half-open probes, named errors | [`reliability/circuit_breaker.py`](src/llm_gateway/reliability/circuit_breaker.py) · [state machine](docs/evidence/architecture/circuit_breaker_state_machine.md) |
| **Two-tier cache** | Exact SHA-256 tier, then FAISS HNSW cosine tier, tenant/model/param namespaces, TTL | [`cache/two_tier.py`](src/llm_gateway/cache/two_tier.py) · [design](docs/evidence/architecture/caching_design.md) |
| **`live_data` bypass** | Skips both cache read and write for prices/inventory | [`tests/routing/integration/test_gateway_phase2.py`](tests/routing/integration/test_gateway_phase2.py) |
| **Cost ledger + `/v1/costs`** | Idempotent SQLite ledger, batch writer, per-day/tenant/model summary | [`billing/cost_ledger.py`](src/llm_gateway/billing/cost_ledger.py) |
| **Observability** | OTel spans (`provider`, `model`, tokens, `cost_usd`, `latency_ms`, `cache_hit`) + Prometheus `/metrics` | [`observability/`](src/llm_gateway/observability/) · [snapshot](data/evidence/prometheus_metrics_snapshot.txt) · [dashboard](docs/evidence/figures/grafana_dashboard.png) |
| **Virtual keys** | SHA-256 hashed keys, scopes, expiry, revocation, rotation, per-key RPM/TPM/budget; SQLite/Postgres + Redis cache | [`auth/key_store.py`](src/llm_gateway/auth/key_store.py) · [`docs/auth/virtual-keys.md`](docs/auth/virtual-keys.md) |
| **PII firewall** | Regex detection + sanitization before routing | [`security/firewall.py`](src/llm_gateway/security/firewall.py) |

## Quick start

```bash
git clone https://github.com/ammmanism/llm-gateway.git
cd llm-gateway
pip install -e ".[dev,ml]"     # ml = sentence-transformers for neural embeddings

export OPENAI_API_KEY=sk-...   # optional; without keys the gateway returns mock responses

# Create a real local virtual key (raw key is printed only once)
export GATEWAY_API_KEY=$(python -c "import asyncio; from llm_gateway.auth.key_store import VirtualKeyStore; print(asyncio.run(VirtualKeyStore().create_key('local', scopes=('generate', 'costs', 'admin')))[0])")

# Production: set DATABASE_URL=postgresql://... to use the shared Postgres store.
# Local demo only: export ALLOW_DEMO_KEYS=true to accept arbitrary sk-* keys.
uvicorn llm_gateway.core.server:app --reload
```

```bash
curl -s localhost:8000/generate \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain vector databases", "model": "gpt-4o"}'

curl -s "localhost:8000/v1/costs?date=$(date -u +%F)" -H "Authorization: Bearer $GATEWAY_API_KEY"
curl -s localhost:8000/metrics | head
```

Without provider keys the gateway runs in simulation mode and marks responses
with `"mock": true`. Routing, caching, limits, and failover are still real.

## Reproduce the evidence

```bash
python benchmarks/gateway_overhead.py        # -> data/evidence/gateway_overhead_benchmark.csv
python benchmarks/semantic_threshold_sweep.py # -> data/evidence/semantic_threshold_sweep.csv
python benchmarks/fallback_recovery.py       # -> data/evidence/fallback_recovery.csv + timeline
python benchmarks/cost_attribution_demo.py   # -> data/evidence/cost_ledger_sample.csv
python benchmarks/metrics_snapshot.py        # -> data/evidence/prometheus_metrics_snapshot.txt
python benchmarks/redis_consistency.py       # requires Redis; -> data/evidence/redis_consistency.csv
python benchmarks/budget_atomic_race.py      # requires Redis; -> data/evidence/budget_atomic_race.csv
python benchmarks/plot_evidence.py           # -> docs/evidence/figures/*.png
```

For coverage and OTLP evidence:

```bash
REDIS_URL=redis://localhost:6379/0 \
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gateway_test \
  pytest tests/ -q --cov=llm_gateway --cov-branch \
  --cov-report=json:data/evidence/coverage.json
python benchmarks/coverage_summary.py

docker compose -f deploy/observability/docker-compose.yml up -d otel-collector
# Run the gateway with OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317,
# send a request, then gracefully stop the collector to flush spans.json.
python benchmarks/otel_span_summary.py
```

The plot script reads the CSVs; it never hard-codes a value.

## Architecture

```mermaid
flowchart TD
    C[Client / SDK] --> M[Auth · structured logs · security headers]
    M --> V[Validation + PII firewall]
    V --> R[Dual-metric rate limiter RPM + TPM]
    R --> Q[Quota + budget]
    Q --> RT[Router: cost / latency / adaptive]
    RT --> CA{Cache enabled?}
    CA -- yes --> X[Exact cache]
    X -- miss --> S[Semantic FAISS cache]
    S -- miss --> CB[Circuit breaker]
    X -- hit --> OUT[Response]
    S -- hit --> OUT
    CB --> P[Provider adapters]
    P -- 429/5xx/open --> F[YAML fallback chain]
    F --> P
    P --> L[Cost ledger + metrics + OTel span]
    L --> OUT
```

## Design decisions

- **Exact before semantic.** Exact hits are cheap and cannot be wrong for the
  same prompt. Semantic search runs only on an exact miss.
- **Fallback only on retryable signals.** The chain advances on 429, 5xx, or an
  open circuit; a validation error stops it.
- **`0.85`, not `0.95`.** The old default matched nothing on the labelled set.
  `0.80` was more aggressive but answered one adjacent-intent query from the
  wrong entry. The sweep is committed so the trade-off is reviewable.
- **Per-attempt cost rows.** Retries and fallbacks get distinct `attempt` values,
  so spend is attributable to the provider that actually served the request.
- **Cache hits are requests.** They are written to the ledger at `$0` with
  `usage_source="cache"` so request counts stay honest.

## Testing

```text
$ python -m pytest tests/ -q
116 passed, 8 warnings in 29.75s (0:00:29)
```

With Redis enabled and branch coverage:

```text
TOTAL  3910 statements, 1656 missed, 906 branches, 567 missed  53%
```

New coverage includes:

- `tests/cache/test_two_tier_cache.py` — exact tier, semantic tier, threshold
  rejection, tenant/model/parameter partitioning, TTL expiry, config validation.
- `tests/billing/test_cost_ledger.py` — idempotency, tenant/day isolation, model
  filtering, cache-hit counting.
- `tests/routing/integration/test_gateway_phase2.py` — HTTP cache hit,
  `live_data` bypass, `/v1/costs` totals.
- `tests/reliability/test_circuit_breaker.py` — state transitions and probe caps.
- `tests/security/test_rate_limiter_redis.py` — Redis RPM/TPM scripts and token
  reconciliation (skipped locally when `REDIS_URL` is absent).
- `tests/observability/test_tracing.py` — OTLP wiring and the disable switch.
- `tests/utils/test_usage.py` — provider usage shapes and explicit estimation
  fallback.

`tests/modality` is quarantined to `_superseded/tests-modality/` with a README;
it targets removed APIs and is not counted above.

## Honest limitations

- The FAISS semantic index is per process. The exact cache, rate limiter, and
  budget counters use Redis when configured; a two-worker consistency check is
  committed, but this is not a high-scale load test.
- Auth is a demonstration API-key/tenant map, not a full virtual-key database.
- Branch coverage is **53.84%**. CI publishes the full report; raising it toward
  80% is the next quality goal.
- Benchmarks use a deterministic fake provider to isolate gateway cost from
  provider network variance. They are not claims about real provider latency.

See [`docs/LESSONS.md`](docs/LESSONS.md) for the engineering notes behind these
choices.

---

<p align="center">
  If this repo helped you reason about gateways, a ⭐ helps others find it.<br>
  Follow <a href="https://github.com/ammmanism">@ammmanism</a> for more systems work.
</p>

## License

MIT — see [LICENSE](LICENSE).
