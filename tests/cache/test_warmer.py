import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from llm_gateway.core.server import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_warm_cache_from_jsonl_parser():
    jsonl_content = (
        '{"query": "Hello", "response": "Hi there", "model": "gpt-4o", "provider": "openai"}\n'
        '{"query": "What is 2+2?", "response": "4", "model": "gpt-4o-mini", "provider": "openai"}\n'
    )
    
    with patch("llm_gateway.cache.warmer.semantic_cache.store_cache", new_callable=AsyncMock) as mock_store:
        from llm_gateway.cache.warmer import warm_cache_from_jsonl
        count = await warm_cache_from_jsonl(jsonl_content, "tenant_free_1")
        assert count == 2
        assert mock_store.call_count == 2
        
        # Verify first call arguments
        _, kwargs = mock_store.call_args_list[0]
        assert kwargs["text"] == "Hello"
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["provider"] == "openai"
        assert kwargs["tenant_id"] == "tenant_free_1"

def test_warm_cache_endpoint():
    jsonl_data = '{"query": "a", "response": "b"}\n'
    
    with patch("llm_gateway.cache.warmer.warm_cache_from_jsonl", new_callable=AsyncMock) as mock_warm:
        mock_warm.return_value = 1
        
        with patch("llm_gateway.core.server.semantic_cache.initialize", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/cache/warm",
                    headers={"Authorization": "Bearer test_key_free"},
                    files={"file": ("test.jsonl", jsonl_data, "text/plain")}
                )
                
                assert response.status_code == 200
                assert response.json() == {"status": "success", "entries_warmed": 1}
                mock_warm.assert_called_once()