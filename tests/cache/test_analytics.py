from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from llm_gateway.core.server import app


@pytest.fixture
def mock_pg_pool():
    pool = AsyncMock()
    pool.acquire = MagicMock()
    conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=conn)
    mock_context.__aexit__ = AsyncMock()
    pool.acquire.return_value = mock_context
    return pool, conn


@pytest.mark.asyncio
async def test_get_cache_analytics(mock_pg_pool):
    pool, conn = mock_pg_pool

    mock_log_row = {
        "total_requests": 10,
        "cache_hits": 7,
        "cache_misses": 3,
        "total_saved_usd": 0.05,
        "avg_hit_latency": 15.0,
        "avg_miss_latency": 450.0,
    }
    conn.fetchrow = AsyncMock(return_value=mock_log_row)

    mock_top_queries = [
        {
            "query_text": "What is 2+2?",
            "hit_count": 5,
            "model": "gpt-4o",
            "provider": "openai",
            "cost_usd": 0.0001,
        },
        {
            "query_text": "Photosynthesis?",
            "hit_count": 2,
            "model": "gpt-4o",
            "provider": "openai",
            "cost_usd": 0.0002,
        },
    ]
    conn.fetch = AsyncMock(return_value=mock_top_queries)

    from llm_gateway.cache.analytics import get_cache_analytics

    tenant_id = "00000000-0000-0000-0000-000000000001"
    stats = await get_cache_analytics(pool, tenant_id)

    assert stats["tenant_id"] == tenant_id
    assert stats["total_requests"] == 10
    assert stats["cache_hits"] == 7
    assert stats["cache_misses"] == 3
    assert stats["cache_hit_rate"] == 0.7
    assert stats["total_saved_usd"] == 0.05
    assert stats["avg_hit_latency_ms"] == 15.0
    assert stats["avg_miss_latency_ms"] == 450.0
    assert len(stats["top_queries"]) == 2
    assert stats["top_queries"][0]["query"] == "What is 2+2?"
    assert stats["top_queries"][0]["hit_count"] == 5


def test_cache_stats_endpoint(mock_pg_pool):
    pool, conn = mock_pg_pool

    mock_stats = {
        "tenant_id": "tenant_free_1",
        "total_requests": 5,
        "cache_hits": 4,
        "cache_misses": 1,
        "cache_hit_rate": 0.8,
    }

    with patch(
        "llm_gateway.cache.analytics.get_cache_analytics", new_callable=AsyncMock
    ) as mock_analytics:
        mock_analytics.return_value = mock_stats

        with patch(
            "llm_gateway.core.server.semantic_cache.initialize", new_callable=AsyncMock
        ):
            with TestClient(app) as client:
                client.app.state.pg_pool = pool

                response = client.get(
                    "/v1/cache/stats",
                    headers={"Authorization": "Bearer sk-test_key_free"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["tenant_id"] == "tenant_free_1"
                assert data["cache_hit_rate"] == 0.8
                mock_analytics.assert_called_once()
