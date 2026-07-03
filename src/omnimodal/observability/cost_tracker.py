"""
Cost Tracker
"""

import logging
from typing import Dict, Any
from .metrics import REQUEST_COST

logger = logging.getLogger(__name__)

class CostTracker:
    @staticmethod
    def track(provider: str, modality: str, cost_usd: float):
        REQUEST_COST.labels(provider=provider, modality=modality).inc(cost_usd)
        logger.info(f"Cost: {provider} {modality} ${cost_usd:.6f}")
