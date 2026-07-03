"""
Pytest configuration and shared fixtures.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from omnimodal.gateway.router import SemanticRouter
from omnimodal.gateway.cost_optimizer import CostOptimizer
from omnimodal.gateway.fallback import FallbackChain
from omnimodal.modalities.text import TextAdapter
from omnimodal.modalities.image import ImageAdapter
from omnimodal.modalities.audio import AudioAdapter
from omnimodal.modalities.video import VideoAdapter


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def sample_text_request():
    return {
        "inputs": [{"type": "text", "content": "Explain quantum computing"}],
        "output_modality": "text",
        "quality": "standard"
    }


@pytest.fixture
def sample_multimodal_request():
    return {
        "inputs": [
            {"type": "text", "content": "A cyberpunk city"},
            {"type": "image", "content": "base64..."}
        ],
        "output_modality": "video",
        "quality": "premium"
    }


@pytest_asyncio.fixture
async def router():
    """Fresh router instance."""
    r = SemanticRouter()
    await r.warmup()
    return r


@pytest_asyncio.fixture
async def cost_optimizer(mock_redis):
    """Cost optimizer with mocked cache."""
    opt = CostOptimizer()
    opt.cache.redis = mock_redis
    return opt


@pytest.fixture
def fallback_chain():
    return FallbackChain()


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Quantum computing uses qubits..."
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 20
    return response


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = "Claude's explanation of quantum computing..."
    response.usage.input_tokens = 10
    response.usage.output_tokens = 20
    return response


@pytest.fixture
def provider_registry():
    """Provider registry mock."""
    registry = MagicMock()
    
    # Mock all providers
    for name in ["openai", "anthropic", "google", "stability", "replicate"]:
        provider = MagicMock()
        provider.name = name
        provider.health_check = AsyncMock(return_value={"status": "healthy"})
        provider.estimate_cost = MagicMock(return_value=0.01)
        provider.estimate_latency = MagicMock(return_value=500)
        registry.register(provider)
    
    return registry
