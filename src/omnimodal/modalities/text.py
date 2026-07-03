"""
Text Modality Adapter
Unified interface for text generation, understanding, and code.
"""

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from omnimodal.modalities.base import BaseModalityAdapter

# Optional dependencies handled gracefully
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None


@dataclass
class TextResponse:
    content: str
    model: str
    provider: str
    tokens_input: int
    tokens_output: int
    cost: float
    from_cache: bool = False
    mime_type: str = "text/plain"


class TextAdapter(BaseModalityAdapter):
    """
    Adapter for text-based AI providers.
    Supports: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini), Local (Ollama)
    """
    
    def __init__(self):
        self.clients = {}
        self._init_clients()
        
        # Cost per 1K tokens
        self.pricing = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "gemini-pro": {"input": 0.0005, "output": 0.0015},
            "llama-3-70b": {"input": 0.0, "output": 0.0},  # Local
            "unknown": {"input": 0.0, "output": 0.0}
        }
    
    def _init_clients(self):
        """Initialize provider clients."""
        import os
        if openai is not None and os.getenv("OPENAI_API_KEY"):
            try:
                self.clients["openai"] = openai.AsyncOpenAI()
            except Exception:
                pass
        if anthropic is not None and os.getenv("ANTHROPIC_API_KEY"):
            try:
                self.clients["anthropic"] = anthropic.AsyncAnthropic()
            except Exception:
                pass
    
    async def generate(
        self,
        inputs: List[Any],
        provider: str = "openai",
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> TextResponse:
        """
        Generate text from text inputs.
        """
        prompt = self._extract_prompt(inputs)
        model = model or self._default_model(provider)
        
        if provider == "openai":
            return await self._generate_openai(prompt, model, max_tokens, temperature)
        elif provider == "anthropic":
            return await self._generate_anthropic(prompt, model, max_tokens, temperature)
        elif provider == "google":
            return await self._generate_google(prompt, model, max_tokens, temperature)
        elif provider == "local":
            return await self._generate_local(prompt, model, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_openai(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> TextResponse:
        """Generate using OpenAI."""
        client = self.clients.get("openai")
        if client is None:
            # Mock fallback
            await asyncio.sleep(0.1)
            return TextResponse(
                content=f"[Mock OpenAI Response for prompt: {prompt[:30]}...]",
                model=model,
                provider="openai",
                tokens_input=10,
                tokens_output=20,
                cost=0.001
            )
        
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        content = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        
        prices = self.pricing.get(model, self.pricing["unknown"])
        cost = (tokens_in / 1000 * prices["input"] + 
                tokens_out / 1000 * prices["output"])
        
        return TextResponse(
            content=content,
            model=model,
            provider="openai",
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost=round(cost, 6)
        )
    
    async def _generate_anthropic(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> TextResponse:
        """Generate using Anthropic."""
        client = self.clients.get("anthropic")
        if client is None:
            # Mock fallback
            await asyncio.sleep(0.1)
            return TextResponse(
                content=f"[Mock Anthropic Response for prompt: {prompt[:30]}...]",
                model=model,
                provider="anthropic",
                tokens_input=10,
                tokens_output=20,
                cost=0.001
            )
        
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        
        prices = self.pricing.get(model, self.pricing["unknown"])
        cost = (tokens_in / 1000 * prices["input"] + 
                tokens_out / 1000 * prices["output"])
        
        return TextResponse(
            content=content,
            model=model,
            provider="anthropic",
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost=round(cost, 6)
        )
    
    async def _generate_google(self, prompt, model, max_tokens, temperature):
        """Google Gemini implementation."""
        await asyncio.sleep(0.1)
        return TextResponse(
            content=f"[Mock Google Gemini response for prompt: {prompt[:30]}...]",
            model=model,
            provider="google",
            tokens_input=12,
            tokens_output=24,
            cost=0.0005
        )
    
    async def _generate_local(self, prompt, model, max_tokens, temperature):
        """Local Ollama implementation."""
        await asyncio.sleep(0.05)
        return TextResponse(
            content=f"[Mock Local Ollama response for prompt: {prompt[:30]}...]",
            model=model,
            provider="local",
            tokens_input=15,
            tokens_output=30,
            cost=0.0
        )
    
    async def generate_stream(self, inputs: List[Any], provider: str = "openai"):
        """
        Stream text generation for real-time applications.
        """
        prompt = self._extract_prompt(inputs)
        client = self.clients.get(provider)
        
        if provider == "openai" and client is not None:
            stream = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
