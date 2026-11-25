import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.auth.key_store import VirtualKeyStore
from llm_gateway.auth.quota_manager import QuotaManager
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.routing.adaptive import AdaptiveRouter
from llm_gateway.security.auth import APIKeyAuthMiddleware
from llm_gateway.security.rate_limiter import RateLimiter
from llm_gateway.utils.embeddings import HashingEmbedder


class NullLedger:
    async def record(self, entry):
        return None


class FakeProvider:
    async def generate(self, prompt, **kwargs):
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
    monkeypatch.setenv("ALLOW_DEMO_KEYS", "false")
    store = VirtualKeyStore(str(tmp_path / "keys.sqlite3"))
    server._key_rate_limiters.clear()
    server._key_budget_enforcers.clear()
    monkeypatch.setattr(server, "cost_ledger", NullLedger())
    monkeypatch.setattr(server, "quota_manager", QuotaManager())
    monkeypatch.setattr(server, "budget_enforcer", BudgetEnforcer(default_budget=100.0))
    monkeypatch.setattr(server, "rate_limiter", RateLimiter(10**6, 10**9))
    monkeypatch.setattr(server, "adaptive_router", AdaptiveRouter())
    monkeypatch.setattr(
        server,
        "two_tier_cache",
        TwoTierCache(CacheManager(), SemanticIndex(HashingEmbedder()), threshold=0.85),
    )
    monkeypatch.setattr(
        server.ProviderFactory,
        "get_provider_for_model",
        staticmethod(lambda model: FakeProvider()),
    )
    app = FastAPI()
    app.add_middleware(APIKeyAuthMiddleware, exclude_paths={"/health"}, key_store=store)
    app.post("/generate")(server.generate)
    with TestClient(app) as client:
        yield client, store


def create_key(store, **limits):
    return asyncio.run(store.create_key("tenant-a", **limits))[0]


def post(client, api_key):
    return client.post(
        "/generate",
        json={"prompt": "key limit probe", "model": "gpt-4o", "live_data": True},
        headers={"Authorization": f"Bearer {api_key}"},
    )


def test_per_key_rpm_limit_is_enforced(gateway):
    client, store = gateway
    api_key = create_key(store, rpm_limit=1)
    assert post(client, api_key).status_code == 200
    assert post(client, api_key).status_code == 429


def test_per_key_tpm_limit_is_enforced(gateway):
    client, store = gateway
    api_key = create_key(store, rpm_limit=100, tpm_limit=100)
    assert post(client, api_key).status_code == 429


def test_per_key_budget_is_enforced(gateway):
    client, store = gateway
    api_key = create_key(store, budget_usd=0.0)
    assert post(client, api_key).status_code == 402


def test_keys_in_same_tenant_have_independent_limits(gateway):
    client, store = gateway
    first = create_key(store, rpm_limit=1)
    second = create_key(store, rpm_limit=1)
    assert post(client, first).status_code == 200
    assert post(client, first).status_code == 429
    assert post(client, second).status_code == 200
