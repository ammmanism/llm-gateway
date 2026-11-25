import os

import pytest

from llm_gateway.auth.key_store import VirtualKeyStore
from llm_gateway.auth.postgres_key_store import PostgresVirtualKeyStore
from llm_gateway.core import server

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.asyncio
async def test_runtime_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("API_KEY_DB_PATH", str(tmp_path / "keys.sqlite3"))

    store, pool = await server._create_virtual_key_store()

    assert isinstance(store, VirtualKeyStore)
    assert pool is None


@pytest.mark.asyncio
@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is required")
async def test_runtime_selects_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.delenv("REDIS_URL", raising=False)

    store, pool = await server._create_virtual_key_store()
    try:
        assert isinstance(store, PostgresVirtualKeyStore)
        raw_key, key = await store.create_key("runtime-tenant")
        assert await store.get_key(raw_key) == key
        assert key.tenant_id == "runtime-tenant"
    finally:
        await pool.close()
