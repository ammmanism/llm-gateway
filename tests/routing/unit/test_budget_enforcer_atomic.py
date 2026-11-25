import asyncio
import os
import uuid

import pytest
import redis.asyncio as redis

from llm_gateway.auth.budget_enforcer import BudgetEnforcer

REDIS_URL = os.environ.get("REDIS_URL")


@pytest.mark.asyncio
async def test_memory_reservation_rejects_amount_above_cap(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    enforcer = BudgetEnforcer(default_budget=1.0)

    first = await enforcer.reserve_budget("tenant-a", 0.75)
    second = await enforcer.reserve_budget("tenant-a", 0.30)

    assert first.allowed is True
    assert first.remaining_usd == pytest.approx(0.25)
    assert second.allowed is False
    assert second.spent_usd == pytest.approx(0.75)
    assert await enforcer.get_spend("tenant-a") == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_concurrent_memory_reservations_never_exceed_cap(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    enforcer = BudgetEnforcer(default_budget=1.0)

    results = await asyncio.gather(
        *(enforcer.reserve_budget("tenant-a", 0.01) for _ in range(150))
    )

    allowed = sum(result.allowed for result in results)
    spent = await enforcer.get_spend("tenant-a")
    assert allowed == 100
    assert spent == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_reconcile_and_release_adjust_reserved_spend(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    enforcer = BudgetEnforcer(default_budget=1.0)

    await enforcer.reserve_budget("tenant-a", 0.20)
    spend = await enforcer.reconcile_cost("tenant-a", 0.20, 0.05)
    assert spend == pytest.approx(0.05)

    await enforcer.reserve_budget("tenant-a", 0.10)
    spend = await enforcer.release_cost("tenant-a", 0.10)
    assert spend == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_reservation_rejects_negative_values(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    enforcer = BudgetEnforcer(default_budget=1.0)

    with pytest.raises(ValueError):
        await enforcer.reserve_budget("tenant-a", -0.01)
    with pytest.raises(ValueError):
        await enforcer.reconcile_cost("tenant-a", 0.01, -0.01)


@pytest.mark.asyncio
@pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL is required")
async def test_concurrent_redis_reservations_are_atomic_across_instances():
    tenant = f"test-budget-{uuid.uuid4().hex}"
    workers = [BudgetEnforcer(default_budget=1.0) for _ in range(2)]
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        results = await asyncio.gather(
            *(
                workers[index % len(workers)].reserve_budget(tenant, 0.01)
                for index in range(150)
            )
        )

        allowed = sum(result.allowed for result in results)
        spent = await workers[0].get_spend(tenant)
        assert allowed == 100
        assert spent == pytest.approx(1.0)
    finally:
        await client.delete(f"budget:{tenant}:spent")
        await client.aclose()
