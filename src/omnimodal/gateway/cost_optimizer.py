"""
Cost Optimizer
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from ..config import settings
from ..cache.multi_level import MultiLevelCache
from ..exceptions import CacheError

logger = logging.getLogger(__name__)

@dataclass
class CostEstimate:
    provider: str
    model: str
    estimated_usd: float
    confidence: float
    optimization_applied: list[str]

class CostOptimizer:
    """
    Reduces API costs through intelligent strategies.
    """

    def __init__(self):
        self.cache = MultiLevelCache()
        self.savings_tracker = {
            "cache_hits": 0,
            "downgrades": 0,
            "provider_arbitrage": 0,
            "total_saved_usd": 0.0
        }
        self.model_downgrade_map = {
            "gpt-4o": "claude-3-haiku",
            "claude-3-opus": "claude-3-sonnet",
            "dall-e-3": "stable-diffusion-3",
        }

    async def optimize(
        self,
        route_decision: Any,
        request: Any,
        complexity: int = 5
    ) -> CostEstimate:
        optimizations = []
        original_cost = route_decision.estimated_cost

        inputs = getattr(request, "inputs", request.get("inputs") if isinstance(request, dict) else None)
        quality = getattr(request, "quality", request.get("quality") if isinstance(request, dict) else "standard")

        # 1. Check cache
        cache_key = self._cache_key(route_decision.modality, str(inputs), quality)
        cached = await self.cache.get(cache_key)
        if cached:
            self.savings_tracker["cache_hits"] += 1
            self.savings_tracker["total_saved_usd"] += original_cost
            return CostEstimate(
                provider="cache",
                model="hit",
                estimated_usd=0.0,
                confidence=1.0,
                optimization_applied=["semantic_cache"]
            )

        # 2. Model downgrade for simple tasks
        if complexity <= 3 and route_decision.model in self.model_downgrade_map:
            cheaper_model = self.model_downgrade_map[route_decision.model]
            savings = original_cost * 0.6
            self.savings_tracker["downgrades"] += 1
            self.savings_tracker["total_saved_usd"] += savings
            optimizations.append("model_downgrade")
            return CostEstimate(
                provider=route_decision.provider,
                model=cheaper_model,
