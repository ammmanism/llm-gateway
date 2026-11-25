from datetime import datetime, timezone

import pytest
import pytest_asyncio

from llm_gateway.billing.cost_ledger import CostEntry, CostLedger


def entry(**overrides) -> CostEntry:
    values = {
        "request_id": "req-1",
        "attempt": 0,
        "tenant_id": "tenant-a",
        "provider": "openai",
        "model": "gpt-4o",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "cost_usd": 0.001,
        "cache_hit": False,
        "usage_source": "provider",
        "occurred_at": datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).isoformat(),
    }
    values.update(overrides)
    return CostEntry(**values)


@pytest_asyncio.fixture
async def ledger(tmp_path):
    instance = CostLedger(str(tmp_path / "ledger.sqlite3"))
    yield instance
    await instance.close()


@pytest.mark.asyncio
async def test_record_and_summarize(ledger):
    await ledger.record(entry())
    await ledger.record(entry(request_id="req-2", completion_tokens=40, cost_usd=0.002))

    summary = await ledger.summarize("tenant-a", "2026-11-24")

    assert summary["request_count"] == 2
    assert summary["prompt_tokens"] == 20
    assert summary["completion_tokens"] == 60
    assert summary["total_cost_usd"] == pytest.approx(0.003)
    assert summary["by_model"]["gpt-4o"] == pytest.approx(0.003)
    assert summary["currency"] == "USD"


@pytest.mark.asyncio
async def test_idempotent_on_request_id_and_attempt(ledger):
    await ledger.record(entry())
    await ledger.record(entry(cost_usd=9.99))

    summary = await ledger.summarize("tenant-a", "2026-11-24")

    assert summary["request_count"] == 1
    assert summary["total_cost_usd"] == pytest.approx(0.001)


@pytest.mark.asyncio
async def test_tenant_and_day_isolation(ledger):
    await ledger.record(entry())
    await ledger.record(entry(request_id="req-2", tenant_id="tenant-b"))
    await ledger.record(
        entry(
            request_id="req-3",
            occurred_at=datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc).isoformat(),
        )
    )

    tenant_a = await ledger.summarize("tenant-a", "2026-11-24")
    tenant_b = await ledger.summarize("tenant-b", "2026-11-24")
    next_day = await ledger.summarize("tenant-a", "2026-11-25")

    assert tenant_a["request_count"] == 1
    assert tenant_b["request_count"] == 1
    assert next_day["request_count"] == 1


@pytest.mark.asyncio
async def test_model_filter_and_cache_hit_count(ledger):
    await ledger.record(entry())
    await ledger.record(
        entry(
            request_id="req-2",
            model="gpt-4o-mini",
            cost_usd=0.0005,
            cache_hit=True,
        )
    )

    filtered = await ledger.summarize("tenant-a", "2026-11-24", model="gpt-4o-mini")
    total = await ledger.summarize("tenant-a", "2026-11-24")

    assert filtered["request_count"] == 1
    assert filtered["by_model"] == {"gpt-4o-mini": pytest.approx(0.0005)}
    assert total["cache_hit_count"] == 1


@pytest.mark.asyncio
async def test_close_releases_sqlite_file(ledger):
    await ledger.record(entry())
    await ledger.close()

    ledger.path.unlink()
