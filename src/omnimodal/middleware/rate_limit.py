"""
Rate Limiting Middleware
"""

import time
import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..config import settings
from ..exceptions import RateLimitError

logger = logging.getLogger(__name__)

class TokenBucket:
    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def consume(self, key: str, tokens: int = 1) -> bool:
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.hmget(key, ["tokens", "last_update"])
        result = await pipe.execute()
        current_tokens = float(result[0][0]) if result[0][0] else self.capacity
        last_update = float(result[0][1]) if result[0][1] else now

        elapsed = now - last_update
        new_tokens = min(self.capacity, current_tokens + elapsed * self.refill_rate)

        if new_tokens < tokens:
            return False

        pipe.hmset(key, {"tokens": new_tokens - tokens, "last_update": now})
        pipe.expire(key, 3600)
        await pipe.execute()
        return True

class RateLimitMiddleware(BaseHTTPMiddleware):
