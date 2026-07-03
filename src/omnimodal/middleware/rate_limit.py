"""
Rate Limiting Middleware
Token bucket algorithm with Redis backend.
"""

import time
from typing import Optional, Callable
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class TokenBucket:
    """
    Distributed token bucket for rate limiting.
    """
    
    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate
