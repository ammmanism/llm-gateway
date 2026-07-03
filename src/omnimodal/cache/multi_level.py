"""
Multi-Level Cache
L1: In-memory (LRU), L2: Redis, L3: Object Storage
"""

import asyncio
import hashlib
import json
import time
import logging
from typing import Optional, Any
from functools import lru_cache

from ..config import settings
from ..exceptions import CacheError

logger = logging.getLogger(__name__)

class LRUCache:
    """Simple in-memory LRU cache with TTL."""
    def __init__(self, maxsize=1000, ttl=300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = {}
        self.timestamps = {}

    def get(self, key):
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key, value):
        if len(self.cache) >= self.maxsize:
            # Evict oldest (not LRU implemented, but simple)
            oldest = min(self.timestamps, key=self.timestamps.get)
            del self.cache[oldest]
            del self.timestamps[oldest]
        self.cache[key] = value
        self.timestamps[key] = time.time()

class RedisCache:
    """Redis-backed cache."""
    def __init__(self, url=None, ttl=3600):
        self.url = url or settings.cache.semantic_cache_url
        self.ttl = ttl
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import aioredis
            self._client = aioredis.from_url(self.url)
        return self._client

    async def get(self, key):
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None

    async def set(self, key, value):
        try:
            client = await self._get_client()
            await client.setex(key, self.ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

class ObjectStorageCache:
    """S3/GCS backed cache for large media."""
    def __init__(self, ttl=86400*30):
        self.ttl = ttl
        # Placeholder for boto3 / google-cloud-storage

    async def get(self, key):
        # Placeholder
        return None

    async def set(self, key, value):
        # Placeholder
        pass

class MultiLevelCache:
    """Orchestrates L1, L2, L3 caches."""
    def __init__(self):
        self.l1 = LRUCache(maxsize=1000, ttl=300)
        self.l2 = RedisCache(ttl=3600)
        self.l3 = ObjectStorageCache(ttl=86400*30)
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Optional[Any]:
        # L1
        value = self.l1.get(key)
        if value is not None:
            self.hits += 1
            logger.debug(f"L1 hit: {key}")
            return value

        # L2
        value = await self.l2.get(key)
        if value is not None:
            self.hits += 1
            self.l1.set(key, value)  # promote to L1
            logger.debug(f"L2 hit: {key}")
            return value

        # L3
        value = await self.l3.get(key)
        if value is not None:
            self.hits += 1
            await self.l2.set(key, value)
            self.l1.set(key, value)
            logger.debug(f"L3 hit: {key}")
            return value

        self.misses += 1
        logger.debug(f"Cache miss: {key}")
        return None

    async def set(self, key: str, value: Any):
        self.l1.set(key, value)
        await self.l2.set(key, value)
        # L3 set only for large objects (placeholders)

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
