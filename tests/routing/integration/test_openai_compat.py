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


class RecordingLedger:
    def __init__(self):
        self.entries = []

    async def record(self, entry):
        self.entries.append(entry)


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.fail_stream = False

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "output": "hello from gateway",
            "provider": "openai",
            "model": kwargs.get("model", "gpt-4o"),
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "mock": True,
        }

    async def stream_generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.fail_stream:
            raise RuntimeError("stream unavailable")
        for chunk in ("hello ", "from ", "stream"):
            yield chunk


@pytest_asyncio.fixture
async def openai_client(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("ALLOW_DEMO_KEYS", "true")
    provider = FakeProvider()
    ledger = RecordingLedger()
    budget = BudgetEnforcer(default_budget=100.0)
    monkeypatch.setattr(server, "cost_ledger", ledger)
    monkeypatch.setattr(server, "quota_manager", QuotaManager())
    monkeypatch.setattr(server, "budget_enforcer", budget)
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
        yield client, http, provider, ledger, budget


@pytest.mark.asyncio
async def test_openai_sdk_non_streaming_completion(openai_client):
    client, _, provider, _, _ = openai_client
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hello"},
        ],
        max_completion_tokens=128,
    )

    assert response.object == "chat.completion"
    assert response.choices[0].message.content == "hello from gateway"
    assert response.usage.total_tokens == 12
    assert provider.calls[0][0] == "[system] be concise [user] hello"
    assert provider.calls[0][1]["max_tokens"] == 128


@pytest.mark.asyncio
async def test_openai_endpoint_uses_exact_cache(openai_client):
    client, _, provider, _, _ = openai_client
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
async def test_openai_sdk_streaming_records_usage_and_cost(openai_client):
    client, _, provider, ledger, budget = openai_client
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "stream this"}],
        stream=True,
        stream_options={"include_usage": True},
    )
    chunks = [chunk async for chunk in stream]

    content = "".join(
        chunk.choices[0].delta.content or "" for chunk in chunks if chunk.choices
    )
    usage = next(chunk.usage for chunk in chunks if chunk.usage is not None)
    assert content == "hello from stream"
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[-2].choices[0].finish_reason == "stop"
    assert usage.completion_tokens > 0
    assert len(ledger.entries) == 1
    assert ledger.entries[0].usage_source == "estimated"
    assert ledger.entries[0].cost_usd > 0
    assert await budget.get_spend("default") > 0
    assert provider.calls[0][1]["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_stream_rate_limit_returns_429_before_sse(openai_client, monkeypatch):
    _, http, _, _, _ = openai_client
    monkeypatch.setattr(
        server, "rate_limiter", RateLimiter(rpm_limit=1, tpm_limit=10**9)
    )
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "first"}],
        "stream": True,
    }
    headers = {"Authorization": "Bearer sk-test"}
    assert (
        await http.post("/v1/chat/completions", headers=headers, json=payload)
    ).status_code == 200
    rejected = await http.post("/v1/chat/completions", headers=headers, json=payload)
    assert rejected.status_code == 429


@pytest.mark.asyncio
async def test_stream_budget_rejection_returns_402_before_sse(openai_client):
    _, http, _, _, budget = openai_client
    budget.default_budget = 0.0
    response = await http.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "no budget"}],
            "stream": True,
        },
    )
    assert response.status_code == 402


@pytest.mark.asyncio
async def test_legacy_stream_uses_same_accounting_pipeline(openai_client):
    _, http, _, ledger, budget = openai_client
    response = await http.post(
        "/generate/stream",
        headers={"Authorization": "Bearer sk-test"},
        json={"prompt": "legacy stream", "model": "gpt-4o"},
    )

    assert response.status_code == 200
    assert '"chunk": "hello "' in response.text
    assert '"usage"' in response.text
    assert '"cost_usd"' in response.text
    assert "data: [DONE]" in response.text
    assert len(ledger.entries) == 1
    assert await budget.get_spend("default") > 0


@pytest.mark.asyncio
async def test_stream_failure_releases_budget_and_writes_no_ledger(openai_client):
    _, http, provider, ledger, budget = openai_client
    provider.fail_stream = True
    response = await http.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "fail stream"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert '"error"' in response.text
    assert "data: [DONE]" in response.text
    assert ledger.entries == []
    assert await budget.get_spend("default") == 0.0
