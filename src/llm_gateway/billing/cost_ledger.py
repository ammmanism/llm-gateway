import asyncio
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CostEntry:
    request_id: str
    attempt: int
    tenant_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cache_hit: bool
    usage_source: str
    occurred_at: str


class CostLedger:
    """Idempotent SQLite usage ledger for local/demo deployments."""

    def __init__(self, path: str = "data/cost_ledger.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: Optional[asyncio.Queue] = None
        self._worker: Optional[asyncio.Task] = None
        self._start_lock: Optional[asyncio.Lock] = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cost_entries (
                    request_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    usage_source TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    day TEXT NOT NULL,
                    PRIMARY KEY (request_id, attempt)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cost_tenant_day "
                "ON cost_entries(tenant_id, day)"
            )

    async def _ensure_worker(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self._worker is not None and not self._worker.done():
                return
            if self._queue is None:
                self._queue = asyncio.Queue()
            self._worker = asyncio.create_task(self._drain())

    async def record(self, entry: CostEntry) -> None:
        """Enqueue an entry; the background writer batches commits."""
        await self._ensure_worker()
        self._queue.put_nowait(entry)

    async def _drain(self) -> None:
        while True:
            entry = await self._queue.get()
            batch = [entry]
            while len(batch) < 200:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            try:
                await asyncio.to_thread(self._write_batch, batch)
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _write_batch(self, entries: List[CostEntry]) -> None:
        rows = []
        for entry in entries:
            occurred = datetime.fromisoformat(entry.occurred_at)
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone.utc)
            day = occurred.astimezone(timezone.utc).date().isoformat()
            rows.append(
                {
                    **asdict(entry),
                    "cache_hit": int(entry.cache_hit),
                    "day": day,
                }
            )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO cost_entries (
                    request_id, attempt, tenant_id, provider, model,
                    prompt_tokens, completion_tokens, cost_usd, cache_hit,
                    usage_source, occurred_at, day
                ) VALUES (
                    :request_id, :attempt, :tenant_id, :provider, :model,
                    :prompt_tokens, :completion_tokens, :cost_usd, :cache_hit,
                    :usage_source, :occurred_at, :day
                )
                """,
                rows,
            )

    async def flush(self) -> None:
        """Wait until every enqueued entry has been committed."""
        if self._queue is not None:
            await self._queue.join()

    async def close(self) -> None:
        """Flush and stop the background writer."""
        await self.flush()
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
    async def summarize(
        self,
        tenant_id: str,
        day: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        await self.flush()
        return await asyncio.to_thread(self._summarize, tenant_id, day, model)

    def _summarize(
        self,
        tenant_id: str,
        day: str,
        model: Optional[str],
    ) -> Dict[str, Any]:
        clauses = ["tenant_id = ?", "day = ?"]
        params: List[Any] = [tenant_id, day]
        if model:
            clauses.append("model = ?")
            params.append(model)
        where = " AND ".join(clauses)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM cost_entries WHERE {where} ORDER BY occurred_at",
                params,
            ).fetchall()
        entries = [dict(row) for row in rows]
        by_model: Dict[str, float] = {}
        for entry in entries:
            by_model[entry["model"]] = (
                by_model.get(entry["model"], 0.0) + entry["cost_usd"]
            )
        return {
            "tenant_id": tenant_id,
            "date": day,
            "currency": "USD",
            "request_count": len(entries),
            "cache_hit_count": sum(entry["cache_hit"] for entry in entries),
            "prompt_tokens": sum(entry["prompt_tokens"] for entry in entries),
            "completion_tokens": sum(
                entry["completion_tokens"] for entry in entries
            ),
            "total_cost_usd": sum(entry["cost_usd"] for entry in entries),
            "by_model": by_model,
            "entries": entries,
        }


def new_entry(**kwargs) -> CostEntry:
    """Build a ledger entry with a UTC timestamp."""
    values = dict(kwargs)
    values.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
    return CostEntry(**values)
