import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.auth.quota_manager import QuotaManager
from llm_gateway.billing.cost_ledger import CostLedger
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.routing.adaptive import AdaptiveRouter
from llm_gateway.security.rate_limiter import RateLimiter
from llm_gateway.utils.embeddings import HashingEmbedder

AUTH = {"Authorization": "Bearer sk-budget-test"}


class FakeProvider:
    fail = False
    calls = 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        return {
            "output": "ok",
            "provider": "openai",
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "mock": True,
        }


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    provider = FakeProvider()
    provider.fail, provider.calls = False, 0
    budget = BudgetEnforcer(default_budget=100.0)
    reserve = AsyncMock(wraps=budget.reserve_budget)
    reconcile = AsyncMock(wraps=budget.reconcile_cost)
    release = AsyncMock(wraps=budget.release_cost)
    monkeypatch.setattr(budget, "reserve_budget", reserve)
    monkeypatch.setattr(budget, "reconcile_cost", reconcile)
    monkeypatch.setattr(budget, "release_cost", release)
    cache = TwoTierCache(
        CacheManager(), SemanticIndex(HashingEmbedder()), threshold=0.85
    )
    monkeypatch.setattr(server, "two_tier_cache", cache)
    monkeypatch.setattr(
        server, "cost_ledger", CostLedger(str(tmp_path / "ledger.sqlite3"))
    )
    monkeypatch.setattr(server, "budget_enforcer", budget)
    monkeypatch.setattr(server, "quota_manager", QuotaManager())
    monkeypatch.setattr(server, "adaptive_router", AdaptiveRouter())
    monkeypatch.setattr(server, "rate_limiter", RateLimiter(10**6, 10**9))
    monkeypatch.setattr(
        server.ProviderFactory,
        "get_provider_for_model",
        staticmethod(lambda model: provider),
    )
    with TestClient(server.app) as client:
        yield client, budget, provider, reserve, reconcile, release


def spend(budget):
    return asyncio.run(budget.get_spend("default"))


def test_success_reconciles_and_cache_hit_skips_reservation(gateway):
    client, budget, _, reserve, reconcile, _ = gateway
    payload = {"prompt": "budget cache probe", "model": "gpt-4o"}
    first = client.post("/generate", json=payload, headers=AUTH)
    second = client.post("/generate", json=payload, headers=AUTH)
    assert first.status_code == second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert reserve.await_count == reconcile.await_count == 1
    assert spend(budget) > 0


def test_provider_failure_releases_reservation(gateway):
    client, budget, provider, _, _, release = gateway
    provider.fail = True
    response = client.post(
        "/generate",
        json={"prompt": "failure", "model": "gpt-4o", "live_data": True},
        headers=AUTH,
    )
    assert response.status_code == 503
    assert release.await_count >= 1
    assert spend(budget) == 0.0


def test_budget_rejection_never_calls_provider(gateway):
    client, budget, provider, reserve, _, _ = gateway
    budget.default_budget = 0.0
    response = client.post(
        "/generate",
        json={"prompt": "reject", "model": "gpt-4o", "live_data": True},
        headers=AUTH,
    )
    assert response.status_code == 402
    assert provider.calls == 0
    assert reserve.await_count == 1
    assert spend(budget) == 0.0
