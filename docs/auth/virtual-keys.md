# Virtual API keys

The gateway stores only SHA-256 hashes of raw API keys. Raw keys are returned
once, at creation or rotation.

## Storage selection

- No `DATABASE_URL`: SQLite at `API_KEY_DB_PATH` (default `data/api_keys.sqlite3`).
- `DATABASE_URL=postgresql://...`: shared Postgres `virtual_keys` table.
- `REDIS_URL` set: a 60-second read-through cache with 10-second negative caching.

## Key policy

Each key has:

- `tenant_id`
- scopes: `generate`, `costs`, `admin`
- optional expiry and revocation timestamp
- RPM and TPM limits
- monthly budget cap

Rate-limit and budget state is scoped by `tenant_id:key_id`; metrics and cost
ledger rows remain attributed to the tenant.

## Python lifecycle

```python
import asyncio
from llm_gateway.auth.key_store import VirtualKeyStore

async def main():
    store = VirtualKeyStore()
    raw_key, metadata = await store.create_key(
        "tenant-a",
        scopes=("generate", "costs"),
        rpm_limit=60,
        tpm_limit=30_000,
        budget_usd=25.0,
    )
    print(raw_key)  # shown only once

    rotated = await store.rotate_key(raw_key)
    await store.revoke_key(raw_key)

asyncio.run(main())
```

`PostgresVirtualKeyStore` exposes the same interface when a shared database is
required.

## Demo mode

Production defaults to `ALLOW_DEMO_KEYS=false`, so unknown keys are rejected.
Set `ALLOW_DEMO_KEYS=true` only for local demos/tests; this restores the legacy
behavior where any `sk-*` key maps through `TENANT_API_KEYS` or `default`.
