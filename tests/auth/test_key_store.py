import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from llm_gateway.auth.key_store import VirtualKeyStore


@pytest.fixture
def store(tmp_path):
    return VirtualKeyStore(str(tmp_path / "keys.sqlite3"))


@pytest.mark.asyncio
async def test_create_and_lookup_hashed_key(store):
    raw_key, key = await store.create_key(
        "tenant-a",
        scopes=("generate", "costs"),
        rpm_limit=25,
        tpm_limit=10_000,
        budget_usd=5.0,
    )

    assert raw_key.startswith("sk-")
    assert key.tenant_id == "tenant-a"
    assert key.scopes == ("generate", "costs")
    assert key.rpm_limit == 25
    assert key.tpm_limit == 10_000
    assert key.budget_usd == 5.0
    assert await store.get_key(raw_key) == key
    assert await store.get_key("sk-invalid") is None

    with sqlite3.connect(store.path) as connection:
        stored_hash = connection.execute(
            "SELECT key_hash FROM virtual_keys"
        ).fetchone()[0]
    assert stored_hash == hashlib.sha256(raw_key.encode()).hexdigest()
    assert raw_key.encode() not in store.path.read_bytes()


@pytest.mark.asyncio
async def test_revoke_key_is_immediate_and_idempotent(store):
    raw_key, _ = await store.create_key("tenant-a")

    assert await store.revoke_key(raw_key) is True
    assert await store.get_key(raw_key) is None
    assert await store.revoke_key(raw_key) is False


@pytest.mark.asyncio
async def test_expired_key_is_not_valid(store):
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    raw_key, _ = await store.create_key("tenant-a", expires_at=expired)

    assert await store.get_key(raw_key) is None


@pytest.mark.asyncio
async def test_validation_rejects_invalid_policy(store):
    with pytest.raises(ValueError):
        await store.create_key("tenant-a", scopes=())
    with pytest.raises(ValueError):
        await store.create_key("tenant-a", rpm_limit=0)
    with pytest.raises(ValueError):
        await store.create_key("tenant-a", budget_usd=-1.0)
