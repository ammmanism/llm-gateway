"""
Pytest configuration and fixtures.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from omnimodal.gateway.router import SemanticRouter
from omnimodal.gateway.cost_optimizer import CostOptimizer
from omnimodal.gateway.fallback import FallbackChain
from omnimodal.modalities.text import TextAdapter
from omnimodal.modalities.image import ImageAdapter
from omnimodal.modalities.audio import AudioAdapter
from omnimodal.modalities.video import VideoAdapter

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
