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
