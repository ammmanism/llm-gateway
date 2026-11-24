from fastapi import Response
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

# Request metrics
request_counter = Counter(
    'llm_gateway_requests_total',
    'Total requests',
    ['tenant_id', 'model', 'provider', 'status']  # status: success, error, cache_hit
)

failure_counter = Counter(
    'llm_gateway_failures_total',
    'Total failures',
    ['tenant_id', 'error_type']  # error_type: validation, rate_limit, quota, budget, provider, all_failed
)

latency_histogram = Histogram(
    'llm_gateway_request_duration_ms',
    'Request latency in ms',
    ['tenant_id', 'model', 'provider'],
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 30000]
)

# Token metrics
prompt_tokens_histogram = Histogram(
    'llm_gateway_prompt_tokens',
    'Prompt tokens per request',
    ['tenant_id', 'model'],
    buckets=[10, 50, 100, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000]
)

completion_tokens_histogram = Histogram(
    'llm_gateway_completion_tokens',
    'Completion tokens per request',
    ['tenant_id', 'model'],
    buckets=[10, 50, 100, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000]
)

# Cost metrics
cost_histogram = Histogram(
    'llm_gateway_cost_usd',
    'Cost per request in USD',
    ['tenant_id', 'model', 'provider'],
    buckets=[0.0001, 0.001, 0.01, 0.1, 1.0, 10.0]
)

total_cost = Counter(
    'llm_gateway_total_cost_usd',
    'Total cost in USD',
    ['tenant_id', 'model', 'provider']
)

tenant_daily_cost = Gauge(
    'llm_gateway_tenant_daily_cost_usd',
    'Daily cost per tenant in USD',
    ['tenant_id']
)

# Cache metrics
cache_hits = Counter(
    'llm_gateway_cache_hits_total',
    'Total cache hits',
    ['tenant_id', 'cache_type']  # cache_type: exact, semantic
)

cache_misses = Counter(
    'llm_gateway_cache_misses_total',
    'Total cache misses',
    ['tenant_id']
)

cache_hit_ratio = Gauge(
    'llm_gateway_cache_hit_ratio',
    'Cache hit ratio (0-1)',
    ['tenant_id', 'cache_type']
)

# Fallback metrics
fallback_attempts = Counter(
    'llm_gateway_fallback_attempts_total',
    'Total fallback attempts',
    ['tenant_id', 'primary_model', 'fallback_model', 'trigger']  # trigger: rate_limit, error_5xx, circuit_open
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'llm_gateway_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)',
    ['provider']
)

circuit_breaker_transitions = Counter(
    'llm_gateway_circuit_breaker_transitions_total',
    'Circuit breaker state transitions',
    ['provider', 'from_state', 'to_state']
)

# Rate limiting metrics
rate_limit_rejections = Counter(
    'llm_gateway_rate_limit_rejections_total',
    'Total rate limit rejections',
    ['tenant_id', 'limit_type']  # limit_type: rpm, tpm
)

rate_limit_remaining = Gauge(
    'llm_gateway_rate_limit_remaining',
    'Remaining rate limit capacity',
    ['tenant_id', 'limit_type']  # limit_type: rpm, tpm
)

# Budget metrics
budget_rejections = Counter(
    'llm_gateway_budget_rejections_total',
    'Total budget rejections',
    ['tenant_id']
)

budget_remaining = Gauge(
    'llm_gateway_budget_remaining_usd',
    'Remaining budget in USD',
    ['tenant_id']
)

# Active streams
active_streams = Gauge(
    'llm_gateway_active_streams',
    'Number of active streaming connections',
    ['tenant_id']
)


def metrics_endpoint() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")


def record_request(tenant_id: str, model: str, provider: str, status: str):
    """Record a request with labels."""
    request_counter.labels(
        tenant_id=tenant_id, model=model, provider=provider, status=status
    ).inc()


def record_failure(tenant_id: str, error_type: str):
    """Record a failure with labels."""
    failure_counter.labels(tenant_id=tenant_id, error_type=error_type).inc()


def record_latency(tenant_id: str, model: str, provider: str, latency_ms: float):
    """Record request latency."""
    latency_histogram.labels(
        tenant_id=tenant_id, model=model, provider=provider
    ).observe(latency_ms)


def record_tokens(tenant_id: str, model: str, prompt_tokens: int, completion_tokens: int):
    """Record token usage."""
    prompt_tokens_histogram.labels(tenant_id=tenant_id, model=model).observe(prompt_tokens)
    completion_tokens_histogram.labels(tenant_id=tenant_id, model=model).observe(completion_tokens)


def record_cost(tenant_id: str, model: str, provider: str, cost_usd: float):
    """Record cost metrics."""
    cost_histogram.labels(tenant_id=tenant_id, model=model, provider=provider).observe(cost_usd)
    total_cost.labels(tenant_id=tenant_id, model=model, provider=provider).inc(cost_usd)


def record_cache_hit(tenant_id: str, cache_type: str):
    """Record a cache hit."""
    cache_hits.labels(tenant_id=tenant_id, cache_type=cache_type).inc()


def record_cache_miss(tenant_id: str):
    """Record a cache miss."""
    cache_misses.labels(tenant_id=tenant_id).inc()


def update_cache_hit_ratio(tenant_id: str, cache_type: str, ratio: float):
    """Update cache hit ratio gauge."""
    cache_hit_ratio.labels(tenant_id=tenant_id, cache_type=cache_type).set(ratio)


def record_fallback(tenant_id: str, primary_model: str, fallback_model: str, trigger: str):
    """Record a fallback attempt."""
    fallback_attempts.labels(
        tenant_id=tenant_id,
        primary_model=primary_model,
        fallback_model=fallback_model,
        trigger=trigger
    ).inc()


def set_circuit_breaker_state(provider: str, state: str):
    """Set circuit breaker state gauge."""
    state_map = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}
    circuit_breaker_state.labels(provider=provider).set(state_map.get(state, 0))


def record_circuit_breaker_transition(provider: str, from_state: str, to_state: str):
    """Record a circuit breaker state transition."""
    circuit_breaker_transitions.labels(
        provider=provider, from_state=from_state, to_state=to_state
    ).inc()


def record_rate_limit_rejection(tenant_id: str, limit_type: str):
    """Record a rate limit rejection."""
    rate_limit_rejections.labels(tenant_id=tenant_id, limit_type=limit_type).inc()


def update_rate_limit_remaining(tenant_id: str, limit_type: str, remaining: int):
    """Update rate limit remaining gauge."""
    rate_limit_remaining.labels(tenant_id=tenant_id, limit_type=limit_type).set(remaining)


def record_budget_rejection(tenant_id: str):
    """Record a budget rejection."""
    budget_rejections.labels(tenant_id=tenant_id).inc()


def update_budget_remaining(tenant_id: str, remaining_usd: float):
    """Update budget remaining gauge."""
    budget_remaining.labels(tenant_id=tenant_id).set(remaining_usd)


def update_active_streams(tenant_id: str, delta: int):
    """Update active streams gauge."""
    active_streams.labels(tenant_id=tenant_id).inc(delta)
