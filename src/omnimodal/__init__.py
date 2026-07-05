"""
OmniModal: Unified Multimodal AI Pipeline
"""

__version__ = "2.0.0"
__author__ = "OmniModal Team"

from .gateway.router import SemanticRouter
from .gateway.cost_optimizer import CostOptimizer
from .gateway.fallback import FallbackChain
from .main import app
from .core import (
    RequestCoalescer,
    AdaptiveConcurrencyLimiter,
    ExperimentEngine,
    PromptRegistry,
    CarbonTracker,
    WatermarkManager,
    JSONSchemaEnforcer,
)

__all__ = [
    "SemanticRouter", "CostOptimizer", "FallbackChain", "app",
    "RequestCoalescer", "AdaptiveConcurrencyLimiter",
    "ExperimentEngine", "PromptRegistry",
    "CarbonTracker", "WatermarkManager", "JSONSchemaEnforcer",
]
