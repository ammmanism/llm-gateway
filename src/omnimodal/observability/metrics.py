"""
Prometheus Metrics Collection
Production-grade observability for the gateway.
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import time
from typing import Optional
from functools import wraps

# ---------------------------------------------
# Application Info
# ---------------------------------------------

APP_INFO = Info("omnimodal_build", "Build information")
APP_INFO.info({"version": "1.0.0", "python": "3.11"})

# ---------------------------------------------
# Request Metrics
# ---------------------------------------------

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

CACHE_HIT_COUNTER = Counter(
    "omnimodal_cache_hits_total",
    "Cache hits by type",
    ["cache_type"]  # semantic, vector
)

CACHE_MISS_COUNTER = Counter(
    "omnimodal_cache_misses_total",
    "Cache misses by type",
    ["cache_type"]
)

# ---------------------------------------------
# Provider Health
# ---------------------------------------------

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

# ---------------------------------------------
# Queue Metrics
# ---------------------------------------------

QUEUE_SIZE = Gauge(
    "omnimodal_queue_size",
    "Current queue size by job type",
    ["job_type"]
)

QUEUE_LATENCY = Histogram(
    "omnimodal_queue_wait_seconds",
    "Time spent waiting in queue",
    ["job_type"]
)

# ---------------------------------------------
# Decorators
# ---------------------------------------------

def track_request(modality: str, provider: str, operation: str = "generate"):
    """Decorator to track request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            status = "success"
            fallback = "false"
            
            try:
                result = await func(*args, **kwargs)
                if getattr(result, "fallback_used", False):
                    fallback = "true"
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start
                REQUEST_COUNT.labels(
                    modality=modality,
                    provider=provider,
                    status=status,
                    fallback_used=fallback
                ).inc()
                REQUEST_LATENCY.labels(
                    modality=modality,
                    provider=provider,
                    operation=operation
                ).observe(duration)
        
        return wrapper
    return decorator


def track_cost(provider: str, modality: str, cost_usd: float):
    """Track API cost."""
    REQUEST_COST.labels(provider=provider, modality=modality).inc(cost_usd)


def track_cache(cache_type: str, hit: bool):
    """Track cache performance."""
    if hit:
        CACHE_HIT_COUNTER.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISS_COUNTER.labels(cache_type=cache_type).inc()


class MetricsCollector:
    """
    Centralized metrics collection with structured logging.
    """
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_cost = 0.0
    
    def record_request(self, modality: str, provider: str, latency_ms: float, cost_usd: float, success: bool = True):
        """Record a complete request metric."""
        self.request_count += 1
        self.total_cost += cost_usd
        
        if not success:
            self.error_count += 1
        
        # Calculate error rate
        error_rate = self.error_count / self.request_count if self.request_count > 0 else 0
        
        return {
            "modality": modality,
            "provider": provider,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "success": success,
            "error_rate": error_rate,
            "total_cost": self.total_cost
        }
