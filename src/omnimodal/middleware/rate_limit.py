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
            
            return True
        except Exception:
            # Fail-open rate limiting if redis throws errors
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    Supports per-user, per-IP, and per-endpoint limits.
    """
    
    def __init__(
        self,
        app,
        redis_client,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.redis = redis_client
        self.bucket = TokenBucket(redis_client, burst_size, requests_per_minute / 60)
    
    async def dispatch(self, request: Request, call_next: Callable):
        client_id = self._get_client_id(request)
        
        allowed = await self.bucket.consume(client_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.bucket.capacity)
        
        # Estimate remaining (fail-safe)
        remaining = await self._get_remaining(client_id)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"api:{api_key}"
        
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        return f"ip:{request.client.host if request.client else 'unknown'}"
    
    async def _get_remaining(self, client_id: str) -> int:
        """Get remaining tokens for client."""
        if self.redis is None:
            return int(self.bucket.local_tokens)
            
        try:
            tokens = await self.redis.hget(f"ratelimit:{client_id}", "tokens")
            return int(float(tokens)) if tokens else self.bucket.capacity
        except Exception:
            return self.bucket.capacity
