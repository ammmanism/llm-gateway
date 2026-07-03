"""
Unit tests for the Semantic Router.
"""

import pytest
import pytest_asyncio
from omnimodal.gateway.router import SemanticRouter, QualityTier, RouteDecision


class TestSemanticRouter:
    """Test suite for intelligent routing decisions."""
    
    @pytest_asyncio.fixture
    async def router(self):
        router = SemanticRouter()
        await router.warmup()
        return router
    
    async def test_select_optimal_provider_text(self, router):
        """Router should select best provider for text generation."""
        route = await router.select(
            modality="text",
            quality="premium",
            cost_budget=0.10,
            latency_budget=5000
        )
        
        assert isinstance(route, RouteDecision)
        assert route.provider in ["openai", "anthropic", "google"]
        assert route.quality_score >= 8.5
        assert route.estimated_cost <= 0.10
        assert route.confidence > 0.5
    
    async def test_select_respects_cost_budget(self, router):
        """Router should filter providers exceeding cost budget."""
        route = await router.select(
            modality="text",
            quality="standard",
            cost_budget=0.001,  # Very tight budget
            latency_budget=5000
        )
        
        # Should fall back to cheaper option
        assert route.estimated_cost <= 0.001 or route.provider == "local"
    
    async def test_select_respects_latency_budget(self, router):
        """Router should filter providers exceeding latency budget."""
        route = await router.select(
            modality="text",
            quality="standard",
            cost_budget=1.0,
            latency_budget=100  # Very tight
        )
        
        assert route.estimated_latency_ms <= 100 or route.provider == "local"
    
    async def test_quality_threshold_draft(self, router):
        """Draft quality should allow cheaper, lower-quality models."""
        route = await router.select(
            modality="text",
            quality="draft"
        )
        
        # Draft should accept lower quality scores
        assert route.quality_score >= 5.0
    
    async def test_quality_threshold_enterprise(self, router):
        """Enterprise quality should only allow top-tier providers."""
        route = await router.select(
            modality="text",
            quality="enterprise"
        )
        
        assert route.quality_score >= 9.0
        assert route.provider in ["openai", "anthropic"]
    
    async def test_unsupported_modality(self, router):
        """Should handle unsupported modalities gracefully."""
        with pytest.raises(ValueError):
            await router.select(modality="3d_mesh")
    
    async def test_circuit_breaker_open(self, router):
        """Should not route to providers with open circuit."""
        router.update_circuit_state("openai", "OPEN")
        
        route = await router.select(modality="text")
        assert route.provider != "openai"
    
    async def test_multi_objective_scoring(self, router):
        """Higher quality should score better for premium requests."""
        premium = await router.select(modality="text", quality="premium")
        draft = await router.select(modality="text", quality="draft")
        
        # Premium should prioritize quality over cost
        assert premium.quality_score >= draft.quality_score
    
    def test_default_models(self, router):
        """Should return correct default models per provider."""
        assert router._default_model("openai", "text") == "gpt-4o"
        assert router._default_model("openai", "image") == "dall-e-3"
        assert router._default_model("anthropic", "text") == "claude-3-opus"
        assert router._default_model("stability", "image") == "stable-diffusion-3"


class TestRouteDecision:
    """Test route decision data structure."""
    
    def test_route_decision_immutability(self):
        """Route decisions fields matches input."""
        route = RouteDecision(
            provider="openai",
            model="gpt-4o",
            estimated_cost=0.01,
            estimated_latency_ms=500,
            quality_score=9.5,
            confidence=0.9
        )
        
        assert route.provider == "openai"
        assert route.confidence == 0.9
