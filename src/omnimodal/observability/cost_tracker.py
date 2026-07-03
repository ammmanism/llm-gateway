"""
Cost Tracker Module
Logs real-time API request pricing.
"""

from typing import Dict


class CostTracker:
    """
    Logs API costs per user or model requests.
    """
    
    def __init__(self):
        self.totals: Dict[str, float] = {}

    def track(self, provider: str, cost: float):
        """Add to provider cost."""
        self.totals[provider] = self.totals.get(provider, 0.0) + cost

    def get_total(self, provider: str) -> float:
        """Get total cost logged."""
        return self.totals.get(provider, 0.0)
