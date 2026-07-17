import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL")
        self._redis = None
        self._connected = False
        self._local: Dict[str, Any] = {}

    async def _ensure_redis(self):
        if self.redis_url and not self._connected:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
                self._connected = True
            except Exception as e:
                logger.warning(f"CacheManager Redis unavailable: {e}")
                self.redis_url = None

    async def get(self, key: str, prompt: str = "", tenant_id: str = "default") -> Optional[Dict[str, Any]]:
        await self._ensure_redis()
        if self._redis:
            try:
                data = await self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
            return None
        return self._local.get(key)

    async def set(self, key: str, value: Dict[str, Any], prompt: str = "", tenant_id: str = "default", ttl: int = 3600):
        await self._ensure_redis()
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value))
            except Exception as e:
                logger.warning(f"CacheManager Redis set failed: {e}")
        else:
            self._local[key] = value
