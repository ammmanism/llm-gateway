import httpx
import openai
import pytest
import pytest_asyncio

from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.auth.quota_manager import QuotaManager
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.routing.adaptive import AdaptiveRouter
from llm_gateway.security.rate_limiter import RateLimiter
from llm_gateway.utils.embeddings import HashingEmbedder


class NullLedger:
    async def record(self, entry):
        return None


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "output": "hello from gateway",
            "provider": "openai",
            "model": kwargs.get("model", "gpt-4o"),
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "mock": True,
        }


@pytest_asyncio.fixture
async def openai_client(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("ALLOW_DEMO_KEYS", "true")
    provider = FakeProvider()
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
        staticmethod(lambda model: provider),
    )
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://gateway"
    ) as http:
        client = openai.AsyncOpenAI(
            api_key="sk-test",
            base_url="http://gateway/v1",
            http_client=http,
        )
        yield client, provider


@pytest.mark.asyncio
async def test_openai_sdk_non_streaming_completion(openai_client):
    client, provider = openai_client

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hello"},
        ],
        max_completion_tokens=128,
    )

    assert response.object == "chat.completion"
    assert response.choices[0].message.role == "assistant"
    assert response.choices[0].message.content == "hello from gateway"
    assert response.usage.prompt_tokens == 5
    assert response.usage.completion_tokens == 7
    assert provider.calls[0][0] == "[system] be concise [user] hello"
    assert provider.calls[0][1]["max_tokens"] == 128


@pytest.mark.asyncio
async def test_openai_endpoint_uses_exact_cache(openai_client):
    client, provider = openai_client
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "cache this"}],
    }

    first = await client.chat.completions.create(**payload)
    second = await client.chat.completions.create(**payload)

    assert first.model_extra["x_gateway"]["cache_hit"] is False
    assert second.model_extra["x_gateway"]["cache_hit"] is True
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_streaming_flag_is_rejected_until_pass_7_3(openai_client):
    client, _ = openai_client
    with pytest.raises(openai.BadRequestError):
        await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hello"}],
            stream=True,
        )
