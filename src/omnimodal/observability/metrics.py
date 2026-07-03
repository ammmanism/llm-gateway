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
