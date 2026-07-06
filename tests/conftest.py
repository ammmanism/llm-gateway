"""
Pytest configuration and fixtures.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from omnimodal.gateway.cost_optimizer import CostOptimizer
from omnimodal.gateway.fallback import FallbackChain
from omnimodal.gateway.router import SemanticRouter


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def mock_redis():
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

@pytest_asyncio.fixture
async def router():
    r = SemanticRouter()
    await r.warmup()
    return r

@pytest_asyncio.fixture
async def cost_optimizer(mock_redis):
    opt = CostOptimizer()
    opt.cache.l2._client = mock_redis
    return opt

@pytest.fixture
def fallback_chain():
    return FallbackChain()

@pytest.fixture
def mock_openai_response():
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Quantum computing uses qubits..."
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 20
    return response

@pytest.fixture
def mock_anthropic_response():
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = "Claude's explanation..."
    response.usage.input_tokens = 10
    response.usage.output_tokens = 20
    return response
