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
