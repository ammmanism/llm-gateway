from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.billing.cost_ledger import CostLedger
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.routing.adaptive import AdaptiveRouter
from llm_gateway.security.rate_limiter import RateLimiter
from llm_gateway.utils.embeddings import HashingEmbedder

AUTH = {"Authorization": "Bearer sk-test-123"}


class FakeProvider:
    async def generate(self, prompt: str, **kwargs):
        return {
            "output": f"answer to {prompt}",
            "provider": "openai",
            "model": kwargs.get("model", "gpt-4o"),
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "mock": False,
        }


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = TwoTierCache(
        exact_cache=CacheManager(),
        semantic_index=SemanticIndex(embedder=HashingEmbedder()),
        threshold=0.95,
    )
    ledger = CostLedger(str(tmp_path / "ledger.sqlite3"))
    monkeypatch.setattr(server, "two_tier_cache", cache)
    monkeypatch.setattr(server, "cost_ledger", ledger)
    monkeypatch.setattr(server, "budget_enforcer", BudgetEnforcer(default_budget=100.0))
    monkeypatch.setattr(server, "adaptive_router", AdaptiveRouter())
    monkeypatch.setattr(
        server,
        "rate_limiter",
        RateLimiter(rpm_limit=10**6, tpm_limit=10**9),
    )
    monkeypatch.setattr(
        server.ProviderFactory,
        "get_provider_for_model",
        staticmethod(lambda model: FakeProvider()),
    )
    with TestClient(server.app) as client:
        yield client, ledger


def test_second_request_hits_exact_cache(gateway):
    client, _ = gateway
    prompt = "phase2 exact cache probe"
    body = {"prompt": prompt, "model": "gpt-4o"}

    first = client.post("/generate", json=body, headers=AUTH)
    second = client.post("/generate", json=body, headers=AUTH)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True
    assert second.json()["cache_tier"] == "exact"
    assert second.json()["cost_usd"] == 0.0


def test_live_data_bypasses_cache(gateway):
    client, _ = gateway
    prompt = "phase2 live data probe"
    body = {"prompt": prompt, "model": "gpt-4o"}

    assert client.post("/generate", json=body, headers=AUTH).status_code == 200
    live = client.post(
        "/generate",
        json={**body, "live_data": True},
        headers=AUTH,
    )

    assert live.status_code == 200, live.text
    assert live.json()["cache_hit"] is False
    assert live.json()["cost_usd"] > 0


def test_cost_endpoint_reports_usage(gateway):
    client, _ = gateway
    day = datetime.now(timezone.utc).date().isoformat()
    body = {"prompt": "phase2 cost ledger probe", "model": "gpt-4o", "live_data": True}

    response = client.post("/generate", json=body, headers=AUTH)
    assert response.status_code == 200, response.text

    costs = client.get(f"/v1/costs?date={day}", headers=AUTH)

    assert costs.status_code == 200, costs.text
    summary = costs.json()
    assert summary["request_count"] == 1
    assert summary["prompt_tokens"] == 5
    assert summary["completion_tokens"] == 7
    assert summary["total_cost_usd"] > 0
    assert summary["by_model"]
