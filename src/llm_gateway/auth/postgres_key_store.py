"""Postgres-backed virtual API keys for multi-replica deployments."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from llm_gateway.auth.key_store import VirtualKey, VirtualKeyStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_keys (
    key_id UUID PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    tenant_id TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    rpm_limit INTEGER NOT NULL,
    tpm_limit INTEGER NOT NULL,
    budget_usd DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_virtual_keys_tenant
ON virtual_keys(tenant_id, created_at DESC);
"""


class PostgresVirtualKeyStore:
    """Durable key store sharing one schema across all gateway replicas."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def initialize(self) -> None:
        await self.pool.execute(SCHEMA)

    @staticmethod
    def _hash_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_key(row: asyncpg.Record) -> VirtualKey:
        return VirtualKey(
            key_id=str(row["key_id"]),
            tenant_id=row["tenant_id"],
            scopes=tuple(row["scopes"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            rpm_limit=int(row["rpm_limit"]),
            tpm_limit=int(row["tpm_limit"]),
            budget_usd=float(row["budget_usd"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _is_active(key: VirtualKey, now: datetime) -> bool:
        return not key.revoked_at and (key.expires_at is None or key.expires_at > now)

    async def _insert(
        self,
        connection: Any,
        tenant_id: str,
        scopes: tuple[str, ...],
        expires_at: datetime | None,
        rpm_limit: int,
        tpm_limit: int,
        budget_usd: float,
    ) -> tuple[str, VirtualKey]:
        raw_key = f"sk-{secrets.token_urlsafe(32)}"
        now = datetime.now(timezone.utc)
        row = await connection.fetchrow(
            "INSERT INTO virtual_keys "
            "(key_id, key_hash, tenant_id, scopes, expires_at, revoked_at, "
            "rpm_limit, tpm_limit, budget_usd, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NULL, $6, $7, $8, $9) RETURNING *",
            uuid.uuid4(),
            self._hash_key(raw_key),
            tenant_id,
            list(scopes),
            expires_at,
            rpm_limit,
            tpm_limit,
            budget_usd,
            now,
        )
        return raw_key, self._row_to_key(row)

    async def create_key(
        self,
        tenant_id: str,
        scopes: tuple[str, ...] = ("generate",),
        expires_at: datetime | None = None,
        rpm_limit: int = 100,
        tpm_limit: int = 50_000,
        budget_usd: float = 10.0,
    ) -> tuple[str, VirtualKey]:
        VirtualKeyStore._validate(scopes, rpm_limit, tpm_limit, budget_usd)
        async with self.pool.acquire() as connection:
            return await self._insert(
                connection,
                tenant_id,
                scopes,
                expires_at,
                rpm_limit,
                tpm_limit,
                budget_usd,
            )

    async def get_key(self, api_key: str) -> VirtualKey | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM virtual_keys WHERE key_hash = $1",
                self._hash_key(api_key),
            )
        if row is None:
            return None
        key = self._row_to_key(row)
        return key if self._is_active(key, datetime.now(timezone.utc)) else None

    async def revoke_key(self, api_key: str) -> bool:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                "UPDATE virtual_keys SET revoked_at = $1 "
                "WHERE key_hash = $2 AND revoked_at IS NULL RETURNING key_id",
                datetime.now(timezone.utc),
                self._hash_key(api_key),
            )
        return row is not None

    async def rotate_key(
        self,
        api_key: str,
        scopes: tuple[str, ...] = ("generate",),
        expires_at: datetime | None = None,
        rpm_limit: int = 100,
        tpm_limit: int = 50_000,
        budget_usd: float = 10.0,
    ) -> tuple[str, VirtualKey] | None:
        VirtualKeyStore._validate(scopes, rpm_limit, tpm_limit, budget_usd)
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                old = await connection.fetchrow(
                    "SELECT * FROM virtual_keys WHERE key_hash = $1 FOR UPDATE",
                    self._hash_key(api_key),
                )
                if old is None:
                    return None
                old_key = self._row_to_key(old)
                if not self._is_active(old_key, datetime.now(timezone.utc)):
                    return None
                rotated = await self._insert(
                    connection,
                    old_key.tenant_id,
                    scopes,
                    expires_at,
                    rpm_limit,
                    tpm_limit,
                    budget_usd,
                )
                await connection.execute(
                    "UPDATE virtual_keys SET revoked_at = $1 WHERE key_id = $2",
                    datetime.now(timezone.utc),
                    uuid.UUID(old_key.key_id),
                )
                return rotated

    async def list_keys(self, tenant_id: str) -> list[VirtualKey]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT * FROM virtual_keys WHERE tenant_id = $1 "
                "ORDER BY created_at DESC",
                tenant_id,
            )
        return [self._row_to_key(row) for row in rows]
