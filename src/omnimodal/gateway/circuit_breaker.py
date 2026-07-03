"""
Circuit Breaker Module wrapper
Imports implementation from fallback to keep structure.
"""

from omnimodal.gateway.fallback import CircuitState, CircuitBreaker

__all__ = ["CircuitState", "CircuitBreaker"]
