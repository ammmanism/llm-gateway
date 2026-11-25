"""Hashed virtual API keys with scopes, limits, expiry, and rotation."""

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_keys (
    key_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    scopes TEXT NOT NULL,
    expires_at TEXT,
    revoked_at TEXT,
    rpm_limit INTEGER NOT NULL,
    tpm_limit INTEGER NOT NULL,
    budget_usd REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_virtual_keys_tenant
ON virtual_keys(tenant_id, created_at DESC);
"""


@dataclass(frozen=True)
class VirtualKey:
    key_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    expires_at: datetime | None
    revoked_at: datetime | None
    rpm_limit: int
    tpm_limit: int
    budget_usd: float
    created_at: datetime


class VirtualKeyStore:
    """SQLite-backed key store; raw keys are returned only at creation."""

    def __init__(self, path: str | None = None):
        self.path = Path(
            path or os.environ.get("API_KEY_DB_PATH", "data/api_keys.sqlite3")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @staticmethod
    def _hash_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    @classmethod
    def _row_to_key(cls, row: sqlite3.Row) -> VirtualKey:
        return VirtualKey(
            key_id=row["key_id"],
            tenant_id=row["tenant_id"],
            scopes=tuple(json.loads(row["scopes"])),
            expires_at=cls._parse_time(row["expires_at"]),
            revoked_at=cls._parse_time(row["revoked_at"]),
            rpm_limit=int(row["rpm_limit"]),
            tpm_limit=int(row["tpm_limit"]),
            budget_usd=float(row["budget_usd"]),
            created_at=cls._parse_time(row["created_at"]),
        )

    @staticmethod
    def _validate(
        scopes: tuple[str, ...], rpm_limit: int, tpm_limit: int, budget_usd: float
    ) -> None:
        if not scopes:
            raise ValueError("at least one scope is required")
        if rpm_limit <= 0 or tpm_limit <= 0:
            raise ValueError("rate limits must be positive")
        if budget_usd < 0:
            raise ValueError("budget_usd must be non-negative")

    def _insert(
        self,
        connection: sqlite3.Connection,
        tenant_id: str,
        scopes: tuple[str, ...],
        expires_at: datetime | None,
        rpm_limit: int,
        tpm_limit: int,
        budget_usd: float,
    ) -> tuple[str, VirtualKey]:
        raw_key = f"sk-{secrets.token_urlsafe(32)}"
        now = datetime.now(timezone.utc)
        values = (
            str(uuid.uuid4()),
            self._hash_key(raw_key),
            tenant_id,
            json.dumps(scopes),
            expires_at.isoformat() if expires_at else None,
            None,
            rpm_limit,
            tpm_limit,
            budget_usd,
            now.isoformat(),
        )
        connection.execute(
            "INSERT INTO virtual_keys VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values
        )
        key = VirtualKey(
            key_id=values[0],
            tenant_id=tenant_id,
            scopes=scopes,
            expires_at=expires_at,
            revoked_at=None,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            budget_usd=budget_usd,
            created_at=now,
        )
        return raw_key, key

    async def create_key(
        self,
        tenant_id: str,
        scopes: tuple[str, ...] = ("generate",),
        expires_at: datetime | None = None,
        rpm_limit: int = 100,
        tpm_limit: int = 50_000,
        budget_usd: float = 10.0,
    ) -> tuple[str, VirtualKey]:
        self._validate(scopes, rpm_limit, tpm_limit, budget_usd)
        return await asyncio.to_thread(
            self._create_sync,
            tenant_id,
            scopes,
            expires_at,
            rpm_limit,
            tpm_limit,
            budget_usd,
        )

    def _create_sync(self, *args) -> tuple[str, VirtualKey]:
        with self._connect() as connection:
            return self._insert(connection, *args)

    async def get_key(self, api_key: str) -> VirtualKey | None:
        return await asyncio.to_thread(self._get_sync, api_key)

    def _get_sync(self, api_key: str) -> VirtualKey | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM virtual_keys WHERE key_hash = ?",
                (self._hash_key(api_key),),
            ).fetchone()
        if row is None:
            return None
        key = self._row_to_key(row)
        now = datetime.now(timezone.utc)
        if key.revoked_at or (key.expires_at and key.expires_at <= now):
            return None
        return key

    async def revoke_key(self, api_key: str) -> bool:
        return await asyncio.to_thread(self._revoke_sync, api_key)

    def _revoke_sync(self, api_key: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE virtual_keys SET revoked_at = ? "
                "WHERE key_hash = ? AND revoked_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), self._hash_key(api_key)),
            )
            return cursor.rowcount > 0
