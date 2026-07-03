"""
Cost Optimizer
Minimizes spend while maintaining quality through caching,
model downgrading, and provider arbitrage.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from functools import lru_cache


@dataclass
class CostEstimate:
    provider: str
    model: str
    estimated_usd: float
    confidence: float  # 0-1, how confident we are in the estimate
    optimization_applied: list[str]  # List of optimizations used


class SemanticCache:
    """
    Two-tier cache: exact match + vector similarity.
    """
    def __init__(self):
        self.exact_cache: Dict[str, Any] = {}  # hash -> response
        self.vector_store = {}  # embedding -> response
        self.hit_count = 0
        self.miss_count = 0
        self.redis = None  # Will be mocked or initialized in tests
    
    def _hash_request(self, modality: str, prompt: str, params: dict) -> str:
        """Create deterministic hash for exact matching."""
        key = f"{modality}:{prompt}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def get(self, modality: str, prompt: str, params: dict) -> Optional[Any]:
        """Check cache with exact match first, then semantic similarity."""
        key = self._hash_request(modality, prompt, params)
        
        # Tier 1: Local cache check (useful for testing & quick replies)
        if key in self.exact_cache:
            self.hit_count += 1
            return self.exact_cache[key]
            
        # Try redis backend if set
        if self.redis is not None:
            try:
                res = await self.redis.get(key)
                if res:
                    self.hit_count += 1
                    # Handle json format
                    return json.loads(res.decode() if isinstance(res, bytes) else res)
            except Exception:
                pass
        
        self.miss_count += 1
