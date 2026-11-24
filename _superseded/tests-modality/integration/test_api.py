"""
Integration tests for the FastAPI application.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from llm_gateway.core.server import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP client with manual lifespan execution."""
    from llm_gateway.core.green_ai import CarbonTracker
    from llm_gateway.routing.cost_optimizer import CostOptimizer
    from llm_gateway.routing.fallback import FallbackChain
    from llm_gateway.routing import SemanticRouter
    from llm_gateway.modality.audio import AudioAdapter
    from llm_gateway.modality.image import ImageAdapter
    from llm_gateway.modality.text import TextAdapter
    from llm_gateway.modality.video import VideoAdapter
    from llm_gateway.observability.metrics import MetricsCollector

    app.state.router = SemanticRouter()
    app.state.cost_optimizer = CostOptimizer()
    app.state.fallback = FallbackChain()
    app.state.metrics = MetricsCollector()
    app.state.carbon_tracker = CarbonTracker()
    app.state.adapters = {
        "text": TextAdapter(),
        "image": ImageAdapter(),
        "audio": AudioAdapter(),
        "video": VideoAdapter(),
    }
    await app.state.router.warmup()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    for adapter in app.state.adapters.values():
        await adapter.close()


class TestHealthEndpoints:
    """Test health and providers endpoints."""

    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    async def test_providers(self, client):
        response = await client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data["providers"]) > 0
        assert all("modalities" in p for p in data["providers"])


class TestGenerationEndpoints:
    """Test generation API with mocked adapters."""

    async def test_generate_text(self, client, monkeypatch):
        """Test text generation endpoint."""

        async def mock_generate(*args, **kwargs):
            return MagicMock(
                content="Generated text",
                mime_type="text/plain",
                provider="openai",
                cost=0.001,
                from_cache=False,
                fallback_used=False,
            )

        monkeypatch.setattr(
            "llm_gateway.modality.text.TextAdapter.generate", mock_generate
        )

        response = await client.post(
            "/v1/generate",
            json={
                "inputs": [{"type": "text", "content": "Hello"}],
                "output_modality": "text",
                "quality": "standard",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Generated text"
        assert data["provider_used"] == "openai"
        assert data["cost_usd"] == 0.001

    async def test_generate_unsupported_modality(self, client):
        """Should return 400 for unsupported modality."""
        response = await client.post(
            "/v1/generate",
            json={
                "inputs": [{"type": "text", "content": "Hello"}],
                "output_modality": "hologram",
                "quality": "standard",
            },
        )
        assert response.status_code == 400


class TestFusionEndpoints:
    """Test multimodal fusion."""

    async def test_fuse_text_to_image(self, client, monkeypatch):
        """Test basic fusion operation."""
        monkeypatch.setattr(
            "llm_gateway.modality.fusion.planner.FusionPlanner.plan",
            MagicMock(
                return_value=MagicMock(
                    stages=[],
                    execute=AsyncMock(
                        return_value=MagicMock(
                            content="base64image", providers=["openai"]
                        )
                    ),
                )
            ),
        )

        response = await client.post(
            "/v1/fuse",
            json={
                "inputs": [{"type": "text", "content": "A cat"}],
                "output_modality": "image",
                "operation": "fuse",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "output" in data
