from prometheus_client import Counter, Histogram

# Request metrics
REQUESTS_TOTAL = Counter(
    "neurocache_requests_total",
    "Total requests processed",
    ["tenant_id", "provider", "model", "status", "is_cache_hit"]
)

REQUEST_DURATION = Histogram(
    "neurocache_request_duration_seconds",
    "Request duration in seconds",
    ["tenant_id", "provider", "model"]
)

TOKENS_TOTAL = Counter(
    "neurocache_tokens_total",
    "Total tokens processed",
    ["tenant_id", "provider", "model", "direction"] # direction in [in, out]
)

# Cache metrics
CACHE_HITS = Counter("neurocache_cache_hits_total", "Total cache hits", ["tenant_id"])
CACHE_MISSES = Counter("neurocache_cache_misses_total", "Total cache misses", ["tenant_id"])
CACHE_SIMILARITY = Histogram("neurocache_cache_similarity_score", "Cache similarity scores", ["tenant_id"])

# Router metrics
ROUTING_DECISIONS = Counter("neurocache_routing_decisions_total", "Routing decisions made", ["provider", "reason"])
PROVIDER_FAILURES = Counter("neurocache_provider_failures_total", "Provider failures by error type", ["provider", "error_type"])

# Billing metrics
COST_USD_TOTAL = Counter("neurocache_cost_usd_total", "Total cost in USD", ["tenant_id", "provider"])
SAVINGS_USD_TOTAL = Counter("neurocache_savings_usd_total", "Total savings in USD", ["tenant_id"])
