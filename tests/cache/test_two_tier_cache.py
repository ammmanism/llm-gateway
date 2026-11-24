import pytest

from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.utils.embeddings import HashingEmbedder


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def build_cache(threshold: float = 0.80, clock: FakeClock | None = None) -> TwoTierCache:
    clock = clock or FakeClock()
    return TwoTierCache(
        exact_cache=CacheManager(clock=clock),
        semantic_index=SemanticIndex(embedder=HashingEmbedder()),
        threshold=threshold,
        exact_ttl=60,
        semantic_ttl=120,
        clock=clock,
    )


def payload(text: str = "answer") -> dict:
    return {"model": "gpt-4o", "provider": "openai", "output": text}


@pytest.mark.asyncio
async def test_exact_tier_hit():
    cache = build_cache()
    await cache.set("What is 2+2?", payload(), "tenant-a", "gpt-4o")

    hit = await cache.get("What is 2+2?", "tenant-a", "gpt-4o")

    assert hit is not None
    assert hit.tier == "exact"
    assert hit.similarity == 1.0
    assert hit.value["output"] == "answer"


@pytest.mark.asyncio
async def test_semantic_tier_hit_for_paraphrase():
    cache = build_cache(threshold=0.80)
    await cache.set("Explain quantum computing", payload("qubits"), "tenant-a", "gpt-4o")

    hit = await cache.get("Explain quantum computing.", "tenant-a", "gpt-4o")

    assert hit is not None
    assert hit.tier == "semantic"
    assert 0.80 <= hit.similarity <= 1.0
    assert hit.value["output"] == "qubits"


@pytest.mark.asyncio
async def test_semantic_threshold_rejects_weak_match():
    cache = build_cache(threshold=0.99)
    await cache.set("Explain quantum computing", payload(), "tenant-a", "gpt-4o")

    hit = await cache.get("Write a poem about the sea", "tenant-a", "gpt-4o")

    assert hit is None


@pytest.mark.asyncio
async def test_tenant_and_model_partitioning():
    cache = build_cache(threshold=0.50)
    await cache.set("Explain quantum computing", payload(), "tenant-a", "gpt-4o")

    assert await cache.get("Explain quantum computing", "tenant-b", "gpt-4o") is None
    assert await cache.get("Explain quantum computing", "tenant-a", "gpt-4o-mini") is None


@pytest.mark.asyncio
async def test_parameter_change_is_a_different_namespace():
    cache = build_cache(threshold=0.50)
    await cache.set(
        "Explain quantum computing",
        payload(),
        "tenant-a",
        "gpt-4o",
        params={"temperature": 0.0},
    )

    assert (
        await cache.get(
            "Explain quantum computing",
            "tenant-a",
            "gpt-4o",
            params={"temperature": 0.9},
        )
        is None
    )


@pytest.mark.asyncio
async def test_expiry_removes_exact_and_semantic_entries():
    clock = FakeClock()
    cache = build_cache(threshold=0.50, clock=clock)
    await cache.set("Explain quantum computing", payload(), "tenant-a", "gpt-4o")

    clock.now += 121

    assert await cache.get("Explain quantum computing", "tenant-a", "gpt-4o") is None


def test_threshold_must_be_in_unit_interval():
    with pytest.raises(ValueError):
        TwoTierCache(threshold=1.5)
