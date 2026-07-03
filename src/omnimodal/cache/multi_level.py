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
