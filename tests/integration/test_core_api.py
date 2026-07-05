import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch


@pytest.fixture
def app():
    from omnimodal.main import app
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestCoreAPIEndpoints:
    @pytest.mark.integration
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "features" in data
        assert data["features"]["deduplication"] is True

    @pytest.mark.integration
    async def test_experiment_create(self, client):
        response = await client.post("/v1/experiments", json={
            "name": "test-exp",
            "hypothesis": "New model is faster",
            "metric": "latency",
            "variants": [
                {"name": "control", "config": {"model": "gpt-4o"}},
                {"name": "treatment", "config": {"model": "claude-3"}},
            ],
            "min_samples": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert "experiment_id" in data
        assert data["status"] == "draft"

    @pytest.mark.integration
    async def test_experiment_results(self, client):
        create_resp = await client.post("/v1/experiments", json={
            "name": "results-test",
            "hypothesis": "Testing results",
            "metric": "quality",
            "variants": [
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
            "min_samples": 10
        })
        exp_id = create_resp.json()["experiment_id"]

        await client.post(f"/v1/experiments/{exp_id}/start")

        results = await client.get(f"/v1/experiments/{exp_id}/results")
        assert results.status_code == 200

    @pytest.mark.integration
    async def test_prompt_create_and_render(self, client):
        create_resp = await client.post("/v1/prompts", json={
            "name": "api-test-prompt",
            "description": "Test from API",
            "initial_prompt": "Hello {name}, welcome to {place}!",
            "variables": ["name", "place"]
        })
        assert create_resp.status_code == 200

        render_resp = await client.post("/v1/prompts/render", json={
            "template_name": "api-test-prompt",
            "variables": {"name": "Alice", "place": "OmniModal"}
        })
        assert render_resp.status_code == 200
        assert render_resp.json()["prompt"] == "Hello Alice, welcome to OmniModal!"

    @pytest.mark.integration
    async def test_validate_schema(self, client):
        response = await client.post("/v1/validate", json={
            "output": '{"name": "Alice", "age": 30}',
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"}
                },
                "required": ["name", "age"]
            }
        })
        assert response.status_code == 200
        assert response.json()["is_valid"] is True

    @pytest.mark.integration
    async def test_validate_invalid_schema(self, client):
        response = await client.post("/v1/validate", json={
            "output": '{"name": "Alice"}',
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"}
                },
                "required": ["name", "age"]
            }
        })
        assert response.status_code == 200
        assert response.json()["is_valid"] is False
        assert any("age" in e for e in response.json()["errors"])

    @pytest.mark.integration
    async def test_carbon_report(self, client):
        response = await client.get("/v1/carbon")
        assert response.status_code == 200
        data = response.json()
        assert "total_co2_grams" in data
        assert "recommendations" in data

    @pytest.mark.integration
    async def test_core_stats(self, client):
        response = await client.get("/v1/stats/core")
        assert response.status_code == 200
        data = response.json()
        assert "coalescer" in data
        assert "concurrency" in data
