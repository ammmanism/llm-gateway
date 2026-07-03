"""
Text Modality Adapter
"""

import asyncio
import logging
from typing import List, Optional, Any
from dataclasses import dataclass
import openai
import anthropic

from .base import BaseModalityAdapter, ModalityResponse
from ..config import settings
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)

@dataclass
class TextResponse(ModalityResponse):
    tokens_input: int = 0
    tokens_output: int = 0

class TextAdapter(BaseModalityAdapter):
    """
    Adapter for text-based AI providers.
    """

    def __init__(self):
        self.clients = {}
        self._init_clients()

        self.pricing = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "gemini-pro": {"input": 0.0005, "output": 0.0015},
            "llama-3-70b": {"input": 0.0, "output": 0.0},
            "meta-llama/Llama-2-70b-chat-hf": {"input": 0.0001, "output": 0.0002},
            "amazon.titan-tg1-large": {"input": 0.001, "output": 0.002},
            "mistral-large-latest": {"input": 0.0003, "output": 0.001},
        }

    def _init_clients(self):
        import os
        if os.getenv("OPENAI_API_KEY"):
            self.clients["openai"] = openai.AsyncOpenAI()
        if os.getenv("ANTHROPIC_API_KEY"):
            self.clients["anthropic"] = anthropic.AsyncAnthropic()
        # Other clients initialized on-demand

    async def generate(self, inputs: List[Any], provider: str = "openai", **kwargs) -> TextResponse:
        prompt = self._extract_prompt(inputs)
        model = kwargs.get("model") or self._default_model(provider)
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.7)

        if provider == "openai":
            return await self._generate_openai(prompt, model, max_tokens, temperature)
        elif provider == "anthropic":
            return await self._generate_anthropic(prompt, model, max_tokens, temperature)
        elif provider == "google":
            return await self._generate_google(prompt, model, max_tokens, temperature)
        elif provider == "local":
            return await self._generate_local(prompt, model, max_tokens, temperature)
        elif provider == "huggingface":
            return await self._generate_huggingface(prompt, model, max_tokens, temperature)
        elif provider == "aws_bedrock":
            return await self._generate_bedrock(prompt, model, max_tokens, temperature)
        elif provider == "mistral":
            return await self._generate_mistral(prompt, model, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _generate_openai(self, prompt: str, model: str, max_tokens: int, temperature: float) -> TextResponse:
        client = self.clients.get("openai")
        if not client:
            raise ProviderError("OpenAI client not initialized")

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            content = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            cost = (tokens_in / 1000 * self.pricing[model]["input"] +
                    tokens_out / 1000 * self.pricing[model]["output"])
            return TextResponse(
                content=content,
                mime_type="text/plain",
                model=model,
                provider="openai",
                cost=round(cost, 6),
                tokens_input=tokens_in,
                tokens_output=tokens_out
            )
        except Exception as e:
            raise ProviderError(f"OpenAI error: {e}")

    async def _generate_anthropic(self, prompt: str, model: str, max_tokens: int, temperature: float) -> TextResponse:
        client = self.clients.get("anthropic")
        if not client:
            raise ProviderError("Anthropic client not initialized")
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            cost = (tokens_in / 1000 * self.pricing[model]["input"] +
                    tokens_out / 1000 * self.pricing[model]["output"])
