"""
OmniModal: Unified Multimodal AI Pipeline
"""

__version__ = "1.0.0"
__author__ = "OmniModal Team"

from .gateway.router import SemanticRouter
from .gateway.cost_optimizer import CostOptimizer
from .gateway.fallback import FallbackChain
from .main import app

__all__ = ["SemanticRouter", "CostOptimizer", "FallbackChain", "app"]
