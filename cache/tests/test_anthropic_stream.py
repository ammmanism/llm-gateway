import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.providers.anthropic import AnthropicProvider

@pytest.mark.asyncio
async def test_anthropic_stream():
    provider = AnthropicProvider()
    
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    
    # We yield simulated Anthropic SSE lines
    async def mock_aiter_lines():
        lines = [
            "event: message_start",
            'data: {"type": "message_start", "message": {"id": "msg_test", "model": "claude-haiku-3.5"}}',
            "",
            "event: content_block_delta",
            'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello "}}',
            "",
            "event: content_block_delta",
            'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "World!"}}',
            "",
            "event: message_delta",
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}',
            "",
            "event: message_stop",
            'data: {"type": "message_stop"}'
        ]
        for line in lines:
            yield line

    mock_response.aiter_lines = mock_aiter_lines
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = MagicMock()
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock()
    mock_client.stream.return_value = mock_context
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in provider.stream(
            model="claude-haiku-3.5",
            messages=[{"role": "user", "content": "Hi"}],
            params={}
        ):
            chunks.append(chunk)
            
        assert len(chunks) == 4 # 2 content deltas, 1 message_delta, 1 [DONE]
        
        # Verify JSON decoding of first chunk
        chunk0 = chunks[0].strip().replace("data: ", "")
        data0 = json.loads(chunk0)
        assert data0["choices"][0]["delta"]["content"] == "Hello "
        
        chunk1 = chunks[1].strip().replace("data: ", "")
        data1 = json.loads(chunk1)
        assert data1["choices"][0]["delta"]["content"] == "World!"
        
        chunk2 = chunks[2].strip().replace("data: ", "")
        data2 = json.loads(chunk2)
        assert data2["choices"][0]["finish_reason"] == "stop"
        
        assert chunks[3] == "data: [DONE]\n\n"