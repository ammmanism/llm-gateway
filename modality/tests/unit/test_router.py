import pytest_asyncio
from omnimodal.gateway.router import RouteDecision, SemanticRouter


class TestSemanticRouter:
    @pytest_asyncio.fixture
    async def router(self):
        router = SemanticRouter()
        await router.warmup()
        return router

    async def test_select_optimal_provider_text(self, router):
        route = await router.select(
            modality="text", quality="premium", cost_budget=0.10, latency_budget=5000
        )
        assert isinstance(route, RouteDecision)
        assert route.provider in ["openai", "anthropic", "google"]
        assert route.quality_score >= 8.5

    async def test_select_respects_cost_budget(self, router):
        route = await router.select(
            modality="text", quality="standard", cost_budget=0.001
        )
        assert route.estimated_cost <= 0.001

    async def test_select_respects_latency_budget(self, router):
        route = await router.select(
            modality="text", quality="standard", latency_budget=100
        )
        assert route.estimated_latency_ms <= 100

    async def test_quality_threshold_draft(self, router):
        route = await router.select(modality="text", quality="draft")
        assert route.quality_score >= 5.0

    async def test_quality_threshold_enterprise(self, router):
        route = await router.select(modality="text", quality="enterprise")
        assert route.quality_score >= 9.0

    async def test_circuit_breaker_open(self, router):
        router.update_circuit_state("openai", "OPEN")
        route = await router.select(modality="text")
        assert route.provider != "openai"
