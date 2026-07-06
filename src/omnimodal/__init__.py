"""
OmniModal: Unified Multimodal AI Pipeline
"""

__version__ = "2.0.0"
__author__ = "OmniModal Team"

from .core import (
    AdaptiveConcurrencyLimiter,
    CarbonTracker,
    ExperimentEngine,
    JSONSchemaEnforcer,
    PromptRegistry,
    RequestCoalescer,
    WatermarkManager,
)
from .gateway.cost_optimizer import CostOptimizer
from .gateway.fallback import FallbackChain
from .gateway.router import SemanticRouter
from .main import app

__all__ = [
    "SemanticRouter", "CostOptimizer", "FallbackChain", "app",
    "RequestCoalescer", "AdaptiveConcurrencyLimiter",
    "ExperimentEngine", "PromptRegistry",
    "CarbonTracker", "WatermarkManager", "JSONSchemaEnforcer",
]
