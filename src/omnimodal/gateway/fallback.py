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
