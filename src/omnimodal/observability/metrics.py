"""
Prometheus Metrics
"""


from prometheus_client import Counter, Gauge, Histogram, Info

APP_INFO = Info("omnimodal_build", "Build information")
APP_INFO.info({"version": "1.0.0", "python": "3.11"})

REQUEST_COUNT = Counter(
    "omnimodal_requests_total",
    "Total requests by modality, provider, and status",
    ["modality", "provider", "status", "fallback_used"]
)

REQUEST_LATENCY = Histogram(
    "omnimodal_request_duration_seconds",
    "Request latency by modality and provider",
    ["modality", "provider", "operation"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

REQUEST_COST = Counter(
    "omnimodal_request_cost_usd_total",
    "Total cost by provider and modality",
    ["provider", "modality"]
)

CACHE_HIT = Counter(
    "omnimodal_cache_hits_total",
    "Cache hits by type",
    ["cache_type"]
)

CACHE_MISS = Counter(
    "omnimodal_cache_misses_total",
    "Cache misses by type",
    ["cache_type"]
)

PROVIDER_HEALTH = Gauge(
    "omnimodal_provider_health",
    "Provider health status (1=healthy, 0=unhealthy)",
    ["provider"]
)

CIRCUIT_BREAKER_STATE = Gauge(
    "omnimodal_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["provider"]
)

class MetricsCollector:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_cost = 0.0

    def record_request(self, modality: str, provider: str, latency_ms: float, cost_usd: float, success: bool = True):
        self.request_count += 1
        self.total_cost += cost_usd
        if not success:
            self.error_count += 1
        return {
            "modality": modality,
            "provider": provider,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "success": success,
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0,
            "total_cost": self.total_cost
        }
