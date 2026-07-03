"""
Fallback Chain & Circuit Breaker
Ensures 99.99% uptime through graceful degradation.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Callable, Optional, Dict, Any
from enum import Enum, auto


class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing fast
    HALF_OPEN = auto()   # Testing recovery


@dataclass
class FallbackResult:
    content: str
    provider: str
    model: str
    cost: float
    from_cache: bool
    fallback_used: bool
    latency_ms: int
    attempts: int
    mime_type: str = "text/plain"


class CircuitBreaker:
    """
    Prevents cascade failures by failing fast when a provider is unhealthy.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.successes = 0
        self.total_calls = 0
    
    def can_execute(self) -> bool:
        """Check if request can proceed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - (self.last_failure_time or 0) > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.total_calls < self.half_open_max_calls
        
        return False
    
    def record_success(self):
        """Record successful call."""
        self.failures = 0
        self.total_calls += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.total_calls = 0
    
    def record_failure(self):
        """Record failed call."""
        self.failures += 1
        self.last_failure_time = time.time()
        self.total_calls += 1
        
        if self.state == CircuitState.CLOSED and self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN


class FallbackChain:
    """
    Orchestrates fallback across multiple providers.
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.fallback_chains = {
            "openai": ["openai", "anthropic", "google", "local"],
            "anthropic": ["anthropic", "openai", "google", "local"],
            "google": ["google", "openai", "local"],
            "replicate": ["replicate", "google", "local"],
            "stability": ["stability", "openai", "local"],
            "local": ["local"],
        }
        self.degradation_map = {
            "video": "image",  # If video fails, return keyframes as images
            "image": "text",   # If image fails, return text description
        }
    
    def _get_circuit(self, provider: str) -> CircuitBreaker:
        """Get or create circuit breaker for provider."""
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = CircuitBreaker()
        return self.circuit_breakers[provider]
    
    async def execute(
        self,
        primary: Any,
        operation: Callable,
        max_attempts: int = 3,
        timeout: float = 30.0
    ) -> FallbackResult:
        """
        Execute operation with fallback chain.
        """
        providers = self.fallback_chains.get(primary.provider, [primary.provider])
        start_time = time.time()
        
        last_error = None
        for attempt, provider in enumerate(providers[:max_attempts]):
            circuit = self._get_circuit(provider)
            
            if not circuit.can_execute():
                continue  # Skip if circuit is open
            
            try:
