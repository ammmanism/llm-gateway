"""
Unit tests for Cost Optimization engine.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from omnimodal.gateway.cost_optimizer import CostOptimizer, SemanticCache


class TestSemanticCache:
    """Test two-tier caching system."""
    
    @pytest_asyncio.fixture
    async def cache(self, mock_redis):
        c = SemanticCache()
        c.redis = mock_redis
        return c
    
    async def test_exact_cache_hit(self, cache):
        """Should return cached response for exact match."""
        cache.redis.get = AsyncMock(return_value=b'{"content": "cached"}')
        
        result = await cache.get("text", "hello", {"quality": "standard"})
        assert result == {"content": "cached"}
        cache.redis.get.assert_called_once()
    
    async def test_cache_miss(self, cache):
        """Should return None on cache miss."""
        cache.redis.get = AsyncMock(return_value=None)
        
        result = await cache.get("text", "hello", {"quality": "standard"})
        assert result is None
    
    async def test_cache_set(self, cache):
        """Should store response in cache."""
        await cache.set("text", "hello", {"quality": "standard"}, {"content": "result"})
        cache.redis.setex.assert_called_once()


class TestCostOptimizer:
    """Test cost optimization strategies."""
    
    @pytest_asyncio.fixture
    async def optimizer(self, mock_redis):
        opt = CostOptimizer()
        opt.cache.redis = mock_redis
        return opt
    
    async def test_cache_optimization(self, optimizer):
        """Cache hit should return zero cost."""
        from omnimodal.gateway.router import RouteDecision
        
        route = RouteDecision(
            provider="openai", model="gpt-4o",
            estimated_cost=0.05, estimated_latency_ms=500,
            quality_score=9.5, confidence=0.9
        )
        
        # Mock cache hit
        optimizer.cache.redis.get = AsyncMock(return_value=b'{"content": "cached"}')
        
        result = await optimizer.optimize(
            route, 
            {"inputs": "test", "quality": "standard", "output_modality": "text"}
        )
        assert result.estimated_usd == 0.0
        assert "semantic_cache" in result.optimization_applied
    
    async def test_model_downgrade(self, optimizer):
        """Simple tasks should use cheaper models."""
        from omnimodal.gateway.router import RouteDecision
        
        route = RouteDecision(
            provider="openai", model="gpt-4o",
            estimated_cost=0.05, estimated_latency_ms=500,
            quality_score=9.5, confidence=0.9
        )
        
        result = await optimizer.optimize(
            route, 
            {"inputs": "test", "quality": "standard", "output_modality": "text"}, 
            complexity=2
        )
        assert "model_downgrade" in result.optimization_applied
        assert result.estimated_usd < 0.05
    
    async def test_no_optimization_needed(self, optimizer):
        """Complex tasks should not be downgraded."""
        from omnimodal.gateway.router import RouteDecision
        
        route = RouteDecision(
            provider="openai", model="gpt-4o",
            estimated_cost=0.05, estimated_latency_ms=500,
            quality_score=9.5, confidence=0.9
        )
        
        result = await optimizer.optimize(
            route, 
            {"inputs": "test", "quality": "standard", "output_modality": "text"}, 
            complexity=9
        )
        assert result.optimization_applied == ["none"]
    
    def test_savings_tracking(self, optimizer):
        """Should track cumulative savings."""
        optimizer.savings_tracker["cache_hits"] = 5
        optimizer.savings_tracker["total_saved_usd"] = 0.25
        
        report = optimizer.get_savings_report()
        assert report["total_optimizations"] == 5
        assert report["total_saved_usd"] == 0.25
