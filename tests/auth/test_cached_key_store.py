import os

import pytest
import pytest_asyncio
import redis.asyncio as redis

from llm_gateway.auth.cached_key_store import CachedVirtualKeyStore
from llm_gateway.auth.key_store import VirtualKeyStore

REDIS_URL = os.environ.get("REDIS_URL")


class CountingStore(VirtualKeyStore):
    def __init__(self, path):
        super().__init__(path)
        self.lookups = 0

    async def get_key(self, api_key):
        self.lookups += 1
        return await super().get_key(api_key)


class BrokenRedis:
    async def get(self, key):
        raise ConnectionError("redis unavailable")

    async def setex(self, key, ttl, value):
        raise ConnectionError("redis unavailable")

    async def delete(self, key):
        raise ConnectionError("redis unavailable")


@pytest_asyncio.fixture
async def cached_store(tmp_path):
    if not REDIS_URL:
        pytest.skip("REDIS_URL is required")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    durable = CountingStore(str(tmp_path / "keys.sqlite3"))
    store = CachedVirtualKeyStore(durable, client)
    yield store, durable
    await client.aclose()


@pytest.mark.asyncio
async def test_positive_cache_avoids_second_durable_lookup(cached_store):
    store, durable = cached_store
    raw_key, key = await store.create_key("tenant-a")

    assert await store.get_key(raw_key) == key
    assert await store.get_key(raw_key) == key
    assert durable.lookups == 1


@pytest.mark.asyncio
async def test_negative_cache_avoids_repeated_misses(cached_store):
    store, durable = cached_store

    assert await store.get_key("sk-missing") is None
    assert await store.get_key("sk-missing") is None
    assert durable.lookups == 1


@pytest.mark.asyncio
async def test_revoke_invalidates_cached_key(cached_store):
    store, durable = cached_store
    raw_key, _ = await store.create_key("tenant-a")
    await store.get_key(raw_key)

    assert await store.revoke_key(raw_key) is True
    assert await store.get_key(raw_key) is None
    assert durable.lookups == 2


@pytest.mark.asyncio
async def test_rotation_invalidates_old_cached_key(cached_store):
    store, durable = cached_store
    old_key, _ = await store.create_key("tenant-a")
    await store.get_key(old_key)

    new_key, _ = await store.rotate_key(old_key)
    assert await store.get_key(old_key) is None
    assert await store.get_key(new_key) is not None
    assert durable.lookups == 3


@pytest.mark.asyncio
async def test_redis_failure_falls_back_to_durable_store(tmp_path):
    durable = CountingStore(str(tmp_path / "keys.sqlite3"))
    store = CachedVirtualKeyStore(durable, BrokenRedis())
    raw_key, key = await store.create_key("tenant-a")

    assert await store.get_key(raw_key) == key
    assert await store.get_key(raw_key) == key
    assert durable.lookups == 2
