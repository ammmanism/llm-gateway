import copy
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """Exact-match cache backed by Redis with a TTL-aware local fallback."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        clock=None,
    ) -> None:
        self.redis_url = redis_url or os.environ.get("REDIS_URL")
        self._redis = None
        self._connected = False
        self._clock = clock or time.monotonic
        self._local: Dict[str, tuple[float, Dict[str, Any]]] = {}

    async def _ensure_redis(self):
        if self.redis_url and not self._connected:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
                await self._redis.ping()
                self._connected = True
            except Exception as exc:
                logger.warning("CacheManager Redis unavailable: %s", exc)
                self.redis_url = None
                self._redis = None

    async def get(
        self,
        key: str,
        prompt: str = "",
        tenant_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """Return an unexpired exact-match value, or None."""
        await self._ensure_redis()
        if self._redis:
            try:
                data = await self._redis.get(key)
                return json.loads(data) if data else None
            except Exception as exc:
                logger.warning("CacheManager Redis get failed: %s", exc)

        item = self._local.get(key)
        if not item:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            self._local.pop(key, None)
            return None
        return copy.deepcopy(value)

    async def set(
        self,
        key: str,
        value: Dict[str, Any],
        prompt: str = "",
        tenant_id: str = "default",
        ttl: int = 3600,
    ) -> None:
        """Store an exact-match value with a positive TTL."""
        if ttl <= 0:
            return
        await self._ensure_redis()
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value))
                return
            except Exception as exc:
                logger.warning("CacheManager Redis set failed: %s", exc)

        self._local[key] = (self._clock() + ttl, copy.deepcopy(value))

    async def delete(self, key: str) -> None:
        """Invalidate an exact-match entry."""
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception as exc:
                logger.warning("CacheManager Redis delete failed: %s", exc)
        self._local.pop(key, None)
