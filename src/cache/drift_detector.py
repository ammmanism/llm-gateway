import math
from datetime import datetime
from typing import Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)

TEMPORAL_MARKERS = {
    "high": ["current", "latest", "today", "now", "this week", "this month", "price of", "stock"],
    "medium": ["recent", "new", "updated", "2025", "2026"],
    "low": ["what is", "explain", "how does", "definition of"]
}

class DriftDetector:
    """
    Monitors cache quality over time.
    Drift Score = max(temporal_decay, consistency_penalty, volatility)
    Range: [0.0, 1.0] where 1.0 = completely stale.
    Invalidation threshold: 0.7
    """
    
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        
    def _detect_temporal_volatility(self, query: str) -> float:
        query_lower = query.lower()
        if any(marker in query_lower for marker in TEMPORAL_MARKERS["high"]):
            return 0.9
        if any(marker in query_lower for marker in TEMPORAL_MARKERS["medium"]):
            return 0.5
        return 0.1  # Most queries are atemporal
        
    def compute_drift_score(self, created_at: datetime, ttl_hours: int, query_text: str, consistency_score: float = 1.0) -> float:
        """
        Compute the drift score for a cache entry.
        consistency_score: 1.0 means perfect consistency (0 penalty). 0.0 means complete inconsistency.
        """
        # 1. Temporal Decay (sigmoid decay centered at TTL midpoint)
        age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
        half_life = ttl_hours / 2
        # Avoid math overflow
        try:
            temporal_decay = 1 / (1 + math.exp(-0.5 * (age_hours - half_life)))
        except OverflowError:
            temporal_decay = 1.0 if age_hours > half_life else 0.0
            
        # 2. Consistency Penalty
        consistency_penalty = 1.0 - consistency_score
        
        # 3. Volatility Factor
        volatility = self._detect_temporal_volatility(query_text)
        
        # Combine with max-dominance
        drift_score = max(
            temporal_decay * 0.4,
            consistency_penalty * 0.8,
            volatility * 0.6
        )
        
        return min(drift_score, 1.0)
        
    def should_invalidate(self, drift_score: float) -> bool:
        return drift_score >= self.threshold
