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
        # Local fallback bucket for when redis is down or None
        self.local_tokens = float(capacity)
        self.local_last_update = time.time()
    
    async def consume(self, key: str, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.
        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        
        if self.redis is None:
            # Local fallback implementation
            elapsed = now - self.local_last_update
            self.local_tokens = min(
                float(self.capacity),
                self.local_tokens + elapsed * self.refill_rate
            )
            self.local_last_update = now
            
            if self.local_tokens < tokens:
                return False
                
            self.local_tokens -= tokens
            return True
            
        try:
            pipe = self.redis.pipeline()
            bucket_key = f"ratelimit:{key}"
            pipe.hmget(bucket_key, ["tokens", "last_update"])
            result = await pipe.execute()
            
            current_tokens = float(result[0][0]) if result[0] and result[0][0] else self.capacity
            last_update = float(result[0][1]) if result[0] and result[0][1] else now
            
            # Calculate refill
            elapsed = now - last_update
            new_tokens = min(
                self.capacity,
                current_tokens + elapsed * self.refill_rate
            )
            
            if new_tokens < tokens:
                return False
            
            # Update bucket
            pipe.hmset(bucket_key, {"tokens": new_tokens - tokens, "last_update": now})
            pipe.expire(bucket_key, 3600)
            await pipe.execute()
            
