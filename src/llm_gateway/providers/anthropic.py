import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict

from llm_gateway.providers.abstract import BaseProvider
from llm_gateway.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError
from llm_gateway.reliability.retry import retry

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseProvider):
    """
    Provider implementation for Anthropic's Claude Messages API.
    
    Optimized for Claude-3 models with native streaming support and 
    automated retries.
    """
    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="anthropic")
        self.default_model = "claude-3-haiku-20240307"

    @retry(max_retries=2, backoff_factor=1.0)
    async def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Generate a complete response using Anthropic's API.
        """
        model = kwargs.get("model", self.default_model)
        try:
            self.circuit_breaker.allow_request()
        except CircuitOpenError as e:
            e.provider = "anthropic"
            raise

        try:
            if not self.api_key:
                # Mock for local development
                await asyncio.sleep(0.15)
                output = f"[Anthropic Mock] Response for: {prompt[:50]}..."
                self.circuit_breaker.record_success()
                return {
                    "provider": "anthropic",
                    "model": model,
                    "output": output,
                    "status": "success",
                    "mock": True
                }

            import httpx
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                output = data["content"][0]["text"]

            self.circuit_breaker.record_success()
            return {
                "provider": "anthropic",
                "model": model,
                "output": output,
                "usage": {
                    "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                },
                "status": "success"
            }
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Anthropic completion failure: {e}")
            raise

    async def stream_generate(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """
        Stream a response using Anthropic's streaming events.
        """
        model = kwargs.get("model", self.default_model)
        try:
            self.circuit_breaker.allow_request()
        except CircuitOpenError as e:
            e.provider = "anthropic"
            raise

        try:
            if not self.api_key:
                # Mock streaming for testing
                for word in ["This", "is", "a", "mock", "Claude", "stream."]:
                    yield word + " "
                    await asyncio.sleep(0.05)
                return

            import httpx
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "messages": [{"role": "user", "content": prompt}],
                "stream": True
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                event = json.loads(data)
                                if event.get("type") == "content_block_delta":
                                    yield event["delta"]["text"]
                                elif event.get("type") == "message_stop":
                                    break
                            except json.JSONDecodeError:
                                continue

            self.circuit_breaker.record_success()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Anthropic stream failure: {e}")
            raise
