"""Redis read-through cache for durable virtual-key stores."""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from llm_gateway.auth.key_store import VirtualKey

MISSING = "__missing__"


class CachedVirtualKeyStore:
    """Cache key metadata while keeping the durable store authoritative."""

    def __init__(self, store: Any, redis_client: Any, ttl_seconds: int = 60):
        self.store = store
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _hash_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def _cache_key(self, api_key: str) -> str:
        return f"virtual-key:{self._hash_key(api_key)}"

    @staticmethod
    def _serialize(key: VirtualKey) -> str:
        data = asdict(key)
        for field in ("expires_at", "revoked_at", "created_at"):
            value = data[field]
            data[field] = value.isoformat() if value else None
        data["scopes"] = list(data["scopes"])
        return json.dumps(data)

    @staticmethod
    def _deserialize(payload: str) -> VirtualKey:
        data = json.loads(payload)
        for field in ("expires_at", "revoked_at", "created_at"):
            value = data[field]
            data[field] = datetime.fromisoformat(value) if value else None
        data["scopes"] = tuple(data["scopes"])
        return VirtualKey(**data)

    async def get_key(self, api_key: str) -> VirtualKey | None:
        cache_key = self._cache_key(api_key)
        try:
            cached = await self.redis.get(cache_key)
        except Exception:
            cached = None
        if cached == MISSING:
            return None
        if cached:
            return self._deserialize(cached)

        key = await self.store.get_key(api_key)
        payload = self._serialize(key) if key else MISSING
        try:
            await self.redis.set(
                cache_key,
                payload,
                ex=self.ttl_seconds if key else 10,
            )
        except Exception:
            pass
        return key

    async def create_key(self, *args, **kwargs):
        return await self.store.create_key(*args, **kwargs)

    async def revoke_key(self, api_key: str) -> bool:
        revoked = await self.store.revoke_key(api_key)
        try:
            await self.redis.delete(self._cache_key(api_key))
        except Exception:
            pass
        return revoked

    async def rotate_key(self, api_key: str, *args, **kwargs):
        rotated = await self.store.rotate_key(api_key, *args, **kwargs)
        try:
            await self.redis.delete(self._cache_key(api_key))
        except Exception:
            pass
        return rotated

    async def list_keys(self, tenant_id: str):
        return await self.store.list_keys(tenant_id)
