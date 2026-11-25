import logging

from llm_gateway.observability.metrics.prometheus import (
    active_streams,
    cache_hit_ratio,
    cost_histogram,
    tenant_daily_cost,
    total_cost,
)
from llm_gateway.observability.metrics.prometheus import (
    record_cache_hit as record_cache_hit_metric,
)
from llm_gateway.observability.metrics.prometheus import (
    record_cost as record_cost_metric,
)
from llm_gateway.observability.metrics.prometheus import (
    update_active_streams as update_active_streams_metric,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "cost_histogram",
    "total_cost",
    "tenant_daily_cost",
    "cache_hit_ratio",
    "active_streams",
    "record_cost",
    "record_cache_hit",
    "update_active_streams",
]

# The actual implementations are in prometheus.py
# This module exists for backward compatibility with existing imports


def record_cost(tenant_id: str, model: str, provider: str, cost_usd: float):
    """Record cost for a request (backward compatibility wrapper)."""
    record_cost_metric(tenant_id, model, provider, cost_usd)


def record_cache_hit(cache_type: str, is_hit: bool):
    """Update cache hit ratio metrics (backward compatibility wrapper)."""
    record_cache_hit_metric(cache_type, is_hit)


def update_active_streams(tenant_id: str, delta: int):
    """Update active streams count (backward compatibility wrapper)."""
    update_active_streams_metric(tenant_id, delta)


# The other functions are imported directly from prometheus.py
