import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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

def test_create_tenant(mock_pg_pool):
    pool, conn = mock_pg_pool
    
    with patch("llm_gateway.core.server.semantic_cache.initialize", new_callable=AsyncMock):
        with TestClient(app) as client:
            client.app.state.pg_pool = pool
            
            payload = {
                "name": "Acme Corp",
                "tier": "pro",
                "rate_limit_rpm": 100,
                "rate_limit_tpm": 50000,
                "spend_cap_usd": 150.0,
                "alert_threshold": 120.0
            }
            
            response = client.post("/admin/tenants", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "success"
            assert "api_key" in data
            assert data["api_key"].startswith("nc_")
            assert "tenant_id" in data
            
            conn.execute.assert_called_once()
            args, _ = conn.execute.call_args
            assert "INSERT INTO tenants" in args[0]
            assert args[3] == "Acme Corp"
            assert args[4] == "pro"

def test_list_tenants(mock_pg_pool):
    pool, conn = mock_pg_pool
    
    mock_row = {
        "id": "tenant-uuid-1",
        "name": "Acme Corp",
        "tier": "pro",
        "rate_limit_rpm": 100,
        "rate_limit_tpm": 50000,
        "spend_cap_usd": 150.0,
        "alert_threshold": 120.0,
        "allowed_models": ["gpt-4o"],
        "cache_threshold": 0.92,
        "cache_ttl_hours": 24,
        "is_active": True
    }
    conn.fetch = AsyncMock(return_value=[mock_row])
    
    with patch("llm_gateway.core.server.semantic_cache.initialize", new_callable=AsyncMock):
        with TestClient(app) as client:
            client.app.state.pg_pool = pool
            
            response = client.get("/admin/tenants")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Acme Corp"
            assert data[0]["tier"] == "pro"
            conn.fetch.assert_called_once_with("SELECT * FROM tenants")

def test_delete_tenant(mock_pg_pool):
    pool, conn = mock_pg_pool
    
    conn.fetchrow = AsyncMock(return_value={"api_key_hash": "mocked_hash"})
    
    mock_redis = AsyncMock()
    mock_tenant_manager = MagicMock()
    mock_tenant_manager.redis = mock_redis
    
    with patch("llm_gateway.core.server.semantic_cache.initialize", new_callable=AsyncMock):
        with TestClient(app) as client:
            client.app.state.pg_pool = pool
            client.app.state.tenant_manager = mock_tenant_manager
            
            response = client.delete("/admin/tenants/tenant-uuid-1")
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            
            conn.fetchrow.assert_called_once_with("SELECT api_key_hash FROM tenants WHERE id = $1", "tenant-uuid-1")
            conn.execute.assert_called_once_with("DELETE FROM tenants WHERE id = $1", "tenant-uuid-1")
            mock_redis.delete.assert_called_once_with("tenant:mocked_hash")