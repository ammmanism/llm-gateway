"""
OmniModal Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import yaml
import json

@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    rate_limit_rps: float = 10.0
    enabled: bool = True
    regions: List[str] = field(default_factory=lambda: ["us-east"])
    cost_model: Dict = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")

@dataclass
class CacheConfig:
    semantic_cache_url: str = "redis://localhost:6379/0"
    vector_cache_url: str = "redis://localhost:6379/1"
    semantic_ttl_seconds: int = 3600
    vector_ttl_seconds: int = 86400
    similarity_threshold: float = 0.95
    max_entries: int = 100000

@dataclass
class RoutingConfig:
    default_quality_threshold: float = 0.7
    default_latency_budget_ms: int = 5000
    enable_cost_optimization: bool = True
