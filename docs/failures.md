# Failure scenarios and design responses

These are **illustrative scenarios**, not claims about real production
incidents. Each scenario points to the test or evidence that exercises the
current behavior.

## Cache stampede

**Scenario:** a popular exact-cache entry expires while many requests miss at
once.

**Current behavior:** the exact tier has TTL support and the gateway records
cache hits/misses in Prometheus. Request coalescing and probabilistic early
expiration are **not implemented**.

**Evidence:** `tests/cache/test_two_tier_cache.py::test_expiry_removes_exact_and_semantic_entries`
and `data/evidence/prometheus_metrics_snapshot.txt`.

## Provider outage

**Scenario:** a provider returns retryable 429/5xx errors until its breaker
opens.

**Current behavior:** fallback advances only for retryable signals or an open
circuit. The breaker caps half-open probes and closes after a successful probe.

**Evidence:** `data/evidence/fallback_recovery.csv`,
`data/evidence/fallback_timeline_events.csv`, and
`tests/reliability/test_circuit_breaker.py`.

## Tenant budget pressure

**Scenario:** a tenant approaches or exceeds its configured spending cap.

**Current behavior:** the gateway checks estimated cost before dispatch and
records actual cost after completion. Redis increments are atomic across
workers, but check-and-reserve is not a single atomic budget reservation.

**Evidence:** `data/evidence/redis_consistency.csv` and
`tests/routing/unit/test_budget_enforcer.py`.

## Trace exporter unavailable

**Scenario:** the OTLP collector is down.

**Current behavior:** the OpenTelemetry SDK retries in the background. Set
`OTEL_SDK_DISABLED=true` for local/test runs that do not need export.

**Evidence:** `tests/observability/test_tracing.py` and
`data/evidence/otel_span_sample.csv` from a successful collector run.
