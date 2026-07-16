from unittest.mock import AsyncMock

import pytest_asyncio
from omnimodal.gateway.cost_optimizer import CostOptimizer
from omnimodal.gateway.router import RouteDecision


class TestCostOptimizer:
    @pytest_asyncio.fixture
    async def optimizer(self, mock_redis):
        opt = CostOptimizer()
        opt.cache.l2._client = mock_redis
        return opt

    async def test_cache_optimization(self, optimizer):
        route = RouteDecision(
            provider="openai",
            model="gpt-4o",
            estimated_cost=0.05,
            estimated_latency_ms=500,
            quality_score=9.5,
            confidence=0.9,
        )
        optimizer.cache.l2.get = AsyncMock(return_value={"content": "cached"})
        result = await optimizer.optimize(route, {"quality": "standard"})
        assert result.estimated_usd == 0.0
        assert "semantic_cache" in result.optimization_applied

    async def test_model_downgrade(self, optimizer):
        route = RouteDecision(
            provider="openai",
            model="gpt-4o",
            estimated_cost=0.05,
            estimated_latency_ms=500,
            quality_score=9.5,
            confidence=0.9,
        )
        result = await optimizer.optimize(route, {"quality": "standard"}, complexity=2)
        assert "model_downgrade" in result.optimization_applied
        assert result.estimated_usd < 0.05
