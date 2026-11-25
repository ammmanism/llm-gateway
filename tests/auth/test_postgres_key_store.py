import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio

from llm_gateway.auth.postgres_key_store import PostgresVirtualKeyStore

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest_asyncio.fixture
async def store():
    pool = await asyncpg.create_pool(DATABASE_URL)
    backend = PostgresVirtualKeyStore(pool)
    await backend.initialize()
    await pool.execute("TRUNCATE virtual_keys")
    yield backend
    await pool.execute("TRUNCATE virtual_keys")
    await pool.close()


@pytest.mark.asyncio
async def test_postgres_create_lookup_and_revoke(store):
    raw_key, key = await store.create_key(
        "tenant-a", scopes=("generate", "costs"), rpm_limit=25, budget_usd=5.0
    )

    assert raw_key.startswith("sk-")
    assert key.tenant_id == "tenant-a"
    assert key.scopes == ("generate", "costs")
    assert await store.get_key(raw_key) == key
    assert await store.revoke_key(raw_key) is True
    assert await store.get_key(raw_key) is None
    assert await store.revoke_key(raw_key) is False


@pytest.mark.asyncio
async def test_postgres_expired_key_is_invalid(store):
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    raw_key, _ = await store.create_key("tenant-a", expires_at=expired)

    assert await store.get_key(raw_key) is None


@pytest.mark.asyncio
async def test_postgres_rotation_and_listing(store):
    old_key, old_metadata = await store.create_key("tenant-a")
    await store.create_key("tenant-b")

    rotated = await store.rotate_key(old_key, scopes=("generate", "admin"))
    assert rotated is not None
    new_key, new_metadata = rotated

    assert new_metadata.tenant_id == old_metadata.tenant_id == "tenant-a"
    assert new_metadata.scopes == ("generate", "admin")
    assert await store.get_key(old_key) is None
    assert await store.get_key(new_key) == new_metadata
    assert len(await store.list_keys("tenant-a")) == 2
    assert len(await store.list_keys("tenant-b")) == 1


@pytest.mark.asyncio
async def test_postgres_unknown_rotation_returns_none(store):
    assert await store.rotate_key(f"sk-{uuid.uuid4().hex}") is None
