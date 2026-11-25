from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_gateway.providers.anthropic import AnthropicProvider


@pytest.mark.asyncio
async def test_anthropic_stream():
    provider = AnthropicProvider()
    provider.api_key = "test-key"

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    # Simulated Anthropic SSE lines
    async def mock_aiter_lines():
        lines = [
            "event: message_start",
            (
                'data: {"type": "message_start", "message": '
                '{"id": "msg_test", "model": "claude-haiku-3.5"}}'
            ),
            "",
            "event: content_block_delta",
            (
                'data: {"type": "content_block_delta", "index": 0, '
                '"delta": {"type": "text_delta", "text": "Hello "}}'
            ),
            "",
            "event: content_block_delta",
            (
                'data: {"type": "content_block_delta", "index": 0, '
                '"delta": {"type": "text_delta", "text": "World!"}}'
            ),
            "",
            "event: message_delta",
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}',
            "",
            "event: message_stop",
            'data: {"type": "message_stop"}',
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
        chunks = [
            chunk
            async for chunk in provider.stream_generate(
                prompt="Hi",
                model="claude-haiku-3.5",
            )
        ]

    # The provider yields decoded text deltas only, not OpenAI-style envelopes.
    assert chunks == ["Hello ", "World!"]
