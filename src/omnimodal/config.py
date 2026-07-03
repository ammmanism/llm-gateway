"""
OmniModal Configuration
Production-grade settings with environment-based overrides.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""
    name: str
    api_key_env: str
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    rate_limit_rps: float = 10.0
    enabled: bool = True
    regions: List[str] = field(default_factory=lambda: ["us-east"])
    cost_model: Dict = field(default_factory=dict)
